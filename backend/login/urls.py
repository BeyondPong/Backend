from django.urls import path

from .views import redirect_to_oauth_provider, oauth_callback

urlpatterns = [
    path("signup/", redirect_to_oauth_provider, name="signup"),
    path("oauth/callback", oauth_callback, name="oauth_callback"),
]
