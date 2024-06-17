from django.urls import path

from . import views


urlpatterns = [
    # 42Seoul social login
    path("oauth/", views.OAuth42SocialLoginView.as_view(), name="callback"),

    # two factor requests(send email, verify code)
    path("two_fa/request/", views.TwoFactorSendCodeView.as_view(), name="two_fa_request"),
    path("two_fa/verify/", views.TwoFactorVerifyCodeView.as_view(), name="two_fa_verify"),
]
