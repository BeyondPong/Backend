from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.conf import settings

import requests


# Create your views here.
def redirect_to_oauth_provider(request):
    params = {
        "client_id": settings.OAUTH_CLIENT_ID,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "response_type": "code",
    }
    request_url = f"{settings.OAUTH_AUTHORIZATION_URL}?client_id={params['client_id']}&redirect_uri={params['redirect_uri']}&response_type={params['response_type']}"
    return redirect(request_url)


def oauth_callback(request):
    code = request.GET.get("code")
    if code:
        token_data = request_access_token(code)
        access_token = token_data("access_token")

        # 사용자 정보 요청
        user_info = get_user_info(access_token)

        # 예: 세션에 정보 저장
        request.session["user_id"] = user_info["id"]
        request.session["user_name"] = user_info["login"]

        # JWT를 생성하여 쿠키에 저장 (필요시 JWT 생성 함수 추가)
        # jwt_token = create_jwt_token(user_info)
        # response.set_cookie("jwt_token", jwt_token, httponly=True)

        return JsonResponse({"message": "Login successful", "user_info": user_info})
    return JsonResponse({"error": "Authorization Failed"}, status=400)


def request_access_token(code):
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.OAUTH_CLIENT_ID,
        "client_secret": settings.OAUTH_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
    }
    response = requests.post(settings.OAUTH_TOKEN_URL, data=data)
    return response.json()


def get_user_info(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}

    user_info_url = "https://api.intra.42.fr/v2/me"
    response = requests.get(user_info_url, headers=headers)
    return response.json()
