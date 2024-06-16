from django.urls import path

from . import views


urlpatterns = [
    path("oauth/", views.OAuth42SocialLoginView.as_view(), name="callback"),
    # test for decode jwt
    # path("oauth/decode/", views.jwtDecode, name="jwt decode test"),

    # todo two factor requests(send email, verify code)
    path("two_fa/request/", views.TwoFactorSendCodeView.as_view(), name="two_fa_request")
    # path("two_fa/verify/", , name="two_fa_verify")
]

"""
[ other team ]
게임 들어가면 홈 버튼 없앰
새로고침하면 몰수 패
"""