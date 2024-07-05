import random
import string

import jwt
import logging
import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_redis import get_redis_connection

from user.models import Member

# just for debugging
logger = logging.getLogger(__name__)


"""
[ 42Seoul social login flow ]
#1 <FE>
    FE >> req(redirect to authorize_url) >> 42 API >> code >> FE
#2 <BE: OAuth42SocialLogin>
    FE >> POST(with code-from-42) >> BE : (localhost:8000/login/callback/)
    BE >> POST(code and data) >> 42 API >> req(ACCESS_TOKEN) >> BE : _get_access_token()
    BE >> GET(ACCESS_TOKEN) >> 42 API >> req(public user-info) >> BE : _get_user_info()
    BE >> save(user-info) or pass(already exist) >> DB : _save_db()
    BE >> jwt(user-info) >> FE
"""


class OAuth42SocialLoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        request_data = {
            "client_id": settings.OAUTH_CLIENT_ID,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "response_type": "code",
        }

        redirect_url = (
            f"{settings.OAUTH_AUTHORIZATION_URL}?client_id={request_data['client_id']}"
            f"&redirect_uri={request_data['redirect_uri']}&response_type={request_data['response_type']}"
        )

        return Response({"redirect_url": redirect_url})

    def post(self, request):
        # get 'code' from request body
        code = request.data.get("code")
        if not code:
            return Response(
                {"error": "Authorization-code parameter is undefined"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # get token-data from _get_access_token
        token_data = self._get_access_token(code)
        if not token_data:
            return Response(
                {"error": "Fail to obtain tokens(access, refresh)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        # get user_info with access_token
        user_info = self._get_user_info(access_token)
        if not user_info:
            return Response(
                {"error": "Fail to fetch user info"}, status=status.HTTP_400_BAD_REQUEST
            )

        # save user-info if not in Member-DB
        user = self._login_or_signup(user_info)
        if isinstance(user, Response):
            return user

        # get jwt-token from user-info(for send FE)
        jwt_token = self._create_jwt_token(user)
        if not jwt_token:
            return Response(
                {"error": "Fail to create jwt token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.debug("========== [LOGIN] SUCCESS: for getting user-info ==========")
        return Response({"token": jwt_token})

    # only used in class
    def _get_access_token(self, code):
        # data struct for post to 42API
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
        }

        # post-requests for getting token_data from 42OAuth-token url with data and return
        token_req = requests.post(settings.OAUTH_TOKEN_URL, data=data)
        if token_req.status_code != 200:
            return None
        token_json = token_req.json()
        token_data = {
            "access_token": token_json.get("access_token"),
            "refresh_token": token_json.get("refresh_token"),
        }
        return token_data

    # only used in class
    def _get_user_info(self, access_token):
        # get-requests for getting user-info
        api_url = settings.OAUTH_API_URL
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            return None
        user_info = response.json()
        return user_info

    def _login_or_signup(self, user_info):
        email = user_info.get("email")
        nickname = user_info.get("login")

        users = Member.objects.filter(nickname=nickname)
        if users.exists():  # origin user
            user = users.first()
            logger.debug("========== ALREADY EXIST USER ==========")
        else:  # new user
            try:
                user = Member.objects.create_user(
                    email=email,
                    nickname=nickname,
                )
                # saved user-status in cache
                cache.set(f"status_{user.nickname}", "new_user", timeout=180)
                logger.debug("========== NEW USER SAVED IN DB ==========")
            except ValueError as e:
                logger.error(f"!!!!!!!! ERROR creating user: {e} !!!!!!!!")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return user

    def _create_jwt_token(self, user):
        payload = {
            "user_id": user.id,
            "nickname": user.nickname,
            "email": user.email,
            "2fa": "false",
        }
        try:
            jwt_token = jwt.encode(
                payload, settings.OAUTH_CLIENT_SECRET, algorithm="HS256"
            )
            logger.debug("========== CREATE JWT TOKEN ==========")
            return jwt_token
        except Exception as e:
            logger.error(f"!!!!!!!! ERROR creating jwt token: {e} !!!!!!!!")
            return None


"""
[ Status for user ]
1. FE >> before Two Factor check if user registered >> BE
   BE >> check cache >> get status(new or origin) and email(intra-email for 2FA) >> FE
"""


class RegistrationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.debug("========== [REGISTRATION_API] ==========")
        # find status from cache
        user_status = cache.get(f"status_{request.user.nickname}")
        if not user_status:
            user_status = "origin_user"
        else:
            cache.delete(f"status_{request.user.nickname}")
        logger.debug(f"{request.user.nickname}: {user_status}")

        return Response({"status": user_status, "email": request.user.email})


"""
[ Two Factor flow ]
1. FE >> req(send or resend) >> BE
   BE >> send-email, save in cache(expired 3minutes) >> email
   BE >> message(success!) >> FE
2. FE >> req(verification_code) >> BE
   BE >> check code from cache-code
        1) SAME >> create_new_jwt_token >> FE
        2) NO >> error(not delete in cache) >> FE
"""


class TwoFactorSendCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.debug("========== 2FA REQUEST FOR SENDING EMAIL ==========")
        # generate 2FA code and send email
        two_fa_code = self._generate_2fa_code()
        self._send_2fa_code_mail(request.user.email, two_fa_code)

        # save 2fa code to Redis with an expiration time (3 minutes)
        cache.set(f"2fa_code_{request.user.nickname}", two_fa_code, timeout=180)

        logger.debug("========== SUCCESS 2FA SENDING EMAIL ==========")
        return Response({"message": "2FA code send to your email"})

    def _generate_2fa_code(self):
        return "".join(random.choices(string.digits, k=6))

    def _send_2fa_code_mail(self, email, two_fa_code):
        subject = "PINGPONG 2FA CODE"
        from_email = settings.DEFAULT_FROM_EMAIL
        to = email
        text_content = f"Your 2FA Code is {two_fa_code}"
        html_content = f"""
        <html>
            <body>
                <h2>🏓PingPong! 2FA Code🏓</h2>
                <p>Your 2FA code is <strong>{two_fa_code}</strong></p>
                <p>Use this code to complete your login.</p>
                <p>Best regards,<br/><em>BeyondPong Team</em> 🎉</p>
            </body>
        </html>
        """
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        msg.send()


class TwoFactorVerifyCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.debug("========== 2FA REQUEST TO VERIFY CODE ==========")
        # get verify-code
        verification_code = request.data.get("verification_code")
        if not verification_code:
            return Response(
                {"error": "Verification code are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check stored-code(from cache) with verify-code(from request-body)
        user = request.user
        stored_code = cache.get(f"2fa_code_{user.nickname}")
        if not stored_code or stored_code != verification_code:
            return Response({"error": "Invalid or expired 2FA code"})

        # delete stored-code from cache
        cache.delete(f"2fa_code_{user.nickname}")

        # get new jwt-token
        new_jwt_token = self._create_new_jwt_token(user)
        if not new_jwt_token:
            return Response(
                {"error": "Fail to create new jwt token"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.debug("========== SUCCESS 2FA AUTHENTICATION ==========")
        return Response({"token": new_jwt_token})

    def _create_new_jwt_token(self, user):
        payload = {
            "user_id": user.id,
            "nickname": user.nickname,
            "email": user.email,
            "2fa": "true",
        }
        try:
            jwt_token = jwt.encode(
                payload, settings.OAUTH_CLIENT_SECRET, algorithm="HS256"
            )
            logger.debug("========== CREATE !!NEW!! JWT TOKEN ==========")
            return jwt_token
        except Exception as e:
            logger.error(f"!!!!!!!! ERROR creating jwt token: {e} !!!!!!!!")
            return None


class MultipleLoginView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.debug("========== MULTIPLE LOGIN REQUEST ==========")
        user = request.user
        redis_conn = get_redis_connection("default")
        is_multiple = bool(redis_conn.sismember(f"login_room_users", user.nickname))
        return Response({"is_multiple": is_multiple}, status=status.HTTP_200_OK)
