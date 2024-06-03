import logging
import requests
from django.http import JsonResponse
# import jwt
from django.shortcuts import redirect
from django.views import View
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# from requests.exceptions import RequestException

# 1. 로그인 api
# 	- 엑세스 토큰으로 사용자의 42 정보를 가져와서 존재하는 사람이면 로그인시키고, 없는 사람인 경우에는 회원가입 시키기
# 	- 회원가입은 유저를 db에 저장해야함
# 2. jwt 토큰 완벽하게 발급하기
# 	- jwt 토큰 내에 넣을 정보 수정
# 3. jwt 토큰을 활용한 인증 인가 구현
# 	- 인증 인가에 대해서 공부해보기
"""
FE >> GET (localhost:8000/login) >> BE >> redirect to authorize_url >> 42 API
"""
class OAuthLoginView(APIView):
    logger.debug("hihihi!!!!!!!!!!!!!!!!!!!!!!!!")
    def get(self, request):
        request_data = {
            "client_id": settings.OAUTH_CLIENT_ID,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "response_type": "code",
        }

        authorize_url = (
            f"{settings.OAUTH_AUTHORIZATION_URL}?client_id={request_data['client_id']}"
            f"&redirect_uri={request_data['redirect_uri']}&response_type={request_data['response_type']}"
        )

        return redirect(authorize_url)


"""
FE >> POST (with code-from-42) >> BE >> code >> 42 API
42 API >> ACCESS_TOKEN >> BE
BE >> ACCESS_TOKEN >> 42 API
42 API >> public user-info >> BE >> jwt(user-info) >> FE
"""
class OAuth42TokenCallback(APIView):
    def post(self, request):
        logger.debug("================Request received================")
        # get 'code' from request body
        code = request.data.get("code")
        if not code:
            logger.debug("================Code parameter is missing================")
            return JsonResponse({"error": "Authorization-code parameter is undefined"}, status=status.HTTP_400_BAD_REQUEST)
        logger.debug(f"================Code received: {code}================")

        # get token-data from get_access_token
        token_data = self.get_access_token(code)
        if not token_data:
            return JsonResponse({"error": "Fail to obtain tokens(access, refresh)"})
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        logger.debug(f"Access token: {access_token}, Refresh token: {refresh_token}")

        # get user_info with access_token
        user_info = self.get_user_info(access_token)
        if 'error' in user_info:
            return JsonResponse({"error": "Fail to fetch user info"}, status=status.HTTP_400_BAD_REQUEST)

        # Save user info or perform login logic here
        # For demonstration, we simply return the user info
        return JsonResponse(user_info)

    def get_access_token(self, code):
        # data struct for post to 42API
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
        }

        # get token_data from 42OAuth-token url with data and return
        token_req = requests.post(settings.OAUTH_TOKEN_URL, data=data)
        if token_req.status_code != 200:
            return None
        token_json = token_req.json()
        logger.debug(f"================Response received: {token_json}================")
        token_data = {
            "access_token": token_json.get("access_token"),
            "refresh_token": token_json.get("refresh_token")
        }
        return token_data

    def get_user_info(self, access_token):
        api_url = "https://api.intra.42.fr/v2/me"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch user info. Status code: {response.status_code}")
            return {'error': 'Failed to fetch user info'}
        user_info = response.json()
        logger.debug(f"User info received: {user_info}")
        return user_info























# OAuth 서비스로 리다이렉트하는 뷰
# def redirect_to_oauth_provider(request):
#     params = {
#         "client_id": settings.OAUTH_CLIENT_ID,
#         "redirect_uri": settings.OAUTH_REDIRECT_URI,
#         "response_type": "code",
#     }
#     request_url = f"{settings.OAUTH_AUTHORIZATION_URL}?client_id={params['client_id']}&redirect_uri={params['redirect_uri']}&response_type={params['response_type']}"
#     return redirect(request_url)
#
#
# # 액세스 토큰 요청
# def request_access_token(code):
#     data = {
#         "grant_type": "authorization_code",
#         "client_id": settings.OAUTH_CLIENT_ID,
#         "client_secret": settings.OAUTH_CLIENT_SECRET,
#         "code": code,
#         "redirect_uri": settings.OAUTH_REDIRECT_URI,
#     }
#     try:
#         response = requests.post(settings.OAUTH_TOKEN_URL, data=data)
#         response.raise_for_status()
#         return response.json()
#     except RequestException as e:
#         return {"error": str(e)}
#
#
# # 사용자 정보 요청
# def get_user_info(access_token):
#     headers = {"Authorization": f"Bearer {access_token}"}
#     try:
#         user_info_url = "https://api.intra.42.fr/v2/me"
#         response = requests.get(user_info_url, headers=headers)
#         response.raise_for_status()
#         return response.json()
#     except RequestException as e:
#         return {"error": str(e)}
#
#
# # JWT 생성
# def create_jwt_token(user_info):
#     payload = {
#         "user_id": user_info["id"],
#         "exp": datetime.utcnow() + timedelta(hours=1),
#         "iat": datetime.utcnow(),
#     }
#     return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
#
#
# # OAuth 콜백 처리 및 JWT 생성
# def oauth_callback(request):
#     code = request.GET.get("code")
#     if code:
#         token_data = request_access_token(code)
#         access_token = token_data.get("access_token")
#
#         if not access_token:
#             return JsonResponse({"error": "Authorization Failed"}, status=400)
#
#         user_info = get_user_info(access_token)
#
#         # JWT 생성 및 쿠키 설정
#         jwt_token = create_jwt_token(user_info)
#         response = JsonResponse({"message": "Login successful", "user_info": user_info})
#         response.set_cookie("jwt_token", jwt_token, httponly=True)
#
#         return response
#
#     return JsonResponse({"error": "Authorization Failed"}, status=400)
