import logging
import requests
# import jwt
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from user.models import Member

# just for debugging
logger = logging.getLogger(__name__)

# 1. 로그인 api (OK)
# 2. jwt 토큰 완벽하게 발급하기 (YET)
# 	- jwt 토큰 내에 넣을 정보 수정
# 3. jwt 토큰을 활용한 인증 인가 구현 (YET)
# 	- 인증 인가에 대해서 공부해보기


"""
#1 <FE>
    FE >> req(redirect to authorize_url) >> 42 API >> code >> FE
#2 <BE: OAuth42SocialLogin>
    FE >> POST(with code-from-42) >> BE : (localhost:8000/login/callback/)
    BE >> POST(code and data) >> 42 API >> req(ACCESS_TOKEN) >> BE : _get_access_token()
    BE >> GET(ACCESS_TOKEN) >> 42 API >> req(public user-info) >> BE : _get_user_info()
    BE >> save(user-info) or pass(already exist) >> DB : _save_db()
    BE >> jwt(user-info) >> FE
"""


class OAuth42SocialLogin(APIView):
    def post(self, request):
        # get 'code' from request body
        code = request.data.get("code")
        if not code:
            return Response({"error": "Authorization-code parameter is undefined"}, status=status.HTTP_400_BAD_REQUEST)

        # get token-data from _get_access_token
        token_data = self._get_access_token(code)
        if not token_data:
            return Response({"error": "Fail to obtain tokens(access, refresh)"}, status=status.HTTP_400_BAD_REQUEST)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        # get user_info with access_token
        user_info = self._get_user_info(access_token)
        if not user_info:
            return Response({"error": "Fail to fetch user info"}, status=status.HTTP_400_BAD_REQUEST)

        # save user-info if not in Member-DB
        user = self._login_or_signup(user_info)

        # TODO: For demonstration, we simply return the user info
        # get jwt-token from user-info(for send FE)
        # jwt_token =

        logger.debug("======= SUCCESS: for getting user-info =======")
        return Response(user_info)

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
            "refresh_token": token_json.get("refresh_token")
        }
        return token_data

    # only used in class
    def _get_user_info(self, access_token):
        # get-requests for getting user-info
        api_url = settings.OAUTH_API_URL
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            return None
        user_info = response.json()
        return user_info

    def _login_or_signup(self, user_info):
        email = user_info.get('email')
        nickname = user_info.get('login')

        users = Member.objects.filter(nickname=nickname)
        if users.exists():
            user = users.first()
            logger.debug("========== ALREADY EXIST USER ==========")
        else:
            try:
                user = Member.objects.create_user(
                    email=email,
                    nickname=nickname,
                )
                logger.debug("========== NEW USER SAVED IN DB ==========")
            except ValueError as e:
                logger.error(f"!!!!!!!! ERROR creating user: {e} !!!!!!!!")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return user