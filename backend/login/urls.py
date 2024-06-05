from django.urls import path

from . import views


urlpatterns = [
    path("oauth/", views.OAuth42SocialLogin.as_view(), name="callback")
    # path("two_fa/request/", , name="two_fa_request")
    # path("two_fa/verify/", , name="two_fa_verify")
]
