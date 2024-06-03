from django.urls import path

# from .views import redirect_to_oauth_provider, oauth_callback
from .views import OAuthLoginView, OAuth42TokenCallback


urlpatterns = [
    # path("signup/", redirect_to_oauth_provider, name="signup"),
    # path("oauth/callback", oauth_callback, name="oauth_callback"),
    path("", OAuthLoginView.as_view(), name="signup"),
    path("callback/", OAuth42TokenCallback.as_view(), name="callback")
    # path("oauth/callback", oauth_callback, name="oauth_callback"),
]
