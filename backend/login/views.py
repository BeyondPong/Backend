import logging
import requests
# import jwt
from django.shortcuts import redirect
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

# just for debugging
logger = logging.getLogger(__name__)

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

        # TODO: Save user info or perform login logic here
        # TODO: For demonstration, we simply return the user info

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
