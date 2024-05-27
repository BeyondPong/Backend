import requests
import jwt

from datetime import datetime, timedelta
from django.http import JsonResponse
from django.shortcuts import redirect
from django.conf import settings
from requests.exceptions import RequestException


# OAuth 서비스로 리다이렉트하는 뷰
def redirect_to_oauth_provider(request):
    params = {
        "client_id": settings.OAUTH_CLIENT_ID,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "response_type": "code",
    }
    request_url = f"{settings.OAUTH_AUTHORIZATION_URL}?client_id={params['client_id']}&redirect_uri={params['redirect_uri']}&response_type={params['response_type']}"
    return redirect(request_url)


# 액세스 토큰 요청
def request_access_token(code):
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.OAUTH_CLIENT_ID,
        "client_secret": settings.OAUTH_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
    }
    try:
        response = requests.post(settings.OAUTH_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        return {"error": str(e)}


# 사용자 정보 요청
def get_user_info(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        user_info_url = "https://api.intra.42.fr/v2/me"
        response = requests.get(user_info_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        return {"error": str(e)}


# JWT 생성
def create_jwt_token(user_info):
    payload = {
        "user_id": user_info["id"],
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# OAuth 콜백 처리 및 JWT 생성
def oauth_callback(request):
    code = request.GET.get("code")
    if code:
        token_data = request_access_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return JsonResponse({"error": "Authorization Failed"}, status=400)

        user_info = get_user_info(access_token)

        # JWT 생성 및 쿠키 설정
        jwt_token = create_jwt_token(user_info)
        response = JsonResponse({"message": "Login successful", "user_info": user_info})
        response.set_cookie("jwt_token", jwt_token, httponly=True)

        return response

    return JsonResponse({"error": "Authorization Failed"}, status=400)
