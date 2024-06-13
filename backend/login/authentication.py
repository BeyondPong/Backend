import jwt
import logging
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from user.models import Member

# just for debugging
logger = logging.getLogger(__name__)


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # except backend-local-home, admin, login
        if request.path.startswith('/admin') or request.path == '/' or request.path == '/login/oauth/':
            logger.debug(f"========== Skipping JWT authentication for path: {request.path} ==========")
            return None

        logger.debug("========== PROCESS REQUEST ==========")
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise AuthenticationFailed("Authorization header is missing")
        try:
            # token: {Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...(=jwt)}
            jwt_token = auth_header.split(" ")[1]
            logger.debug(f"JWT_token: {jwt_token}")
            payload = self._decode_jwt(jwt_token)
            if not payload:
                raise AuthenticationFailed("Invalid jwt-token")
            try:
                user = Member.objects.get(nickname=payload["nickname"])
                # request.user = user
                # request.auth = jwt_token
                logger.debug(f"========= Authenticated user: {user.nickname}=========")
            except Member.DoesNotExist:
                raise AuthenticationFailed("User not found")
        except IndexError:
            # error for split-jwt token
            raise AuthenticationFailed("Invalid jwt-token-header(split)")
        # this method must return (user, auth) tuple-form -> DRF auto-settings to Request
        return user, jwt_token

    @classmethod
    def _decode_jwt(self, jwt_token):
        try:
            payload = jwt.decode(jwt_token, settings.OAUTH_CLIENT_SECRET, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.error("========== ERROR: expired signature ==========")
            return None
        except jwt.InvalidTokenError:
            logger.error("========== ERROR: invalid token(decoding) ==========")
            return None
