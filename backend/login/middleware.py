import jwt
import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status
from rest_framework.response import Response

from user.models import Member

# just for debugging
logger = logging.getLogger(__name__)


class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        logger.debug("========== PROCESS REQUEST ==========")
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                # token: {Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...(=jwt)}
                jwt_token = auth_header.split(" ")[1]
                logger.debug(f"JWT_token: {jwt_token}")
                payload = self._decode_jwt(jwt_token)
                if not payload:
                    return Response({"error": "Invalid jwt-token"}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    user = Member.objects.get(nickname=payload["nickname"])
                    request.user = user
                    request.auth = jwt_token
                    logger.debug(f"========= Authenticated user: {user.nickname}=========")
                except Member.DoesNotExist:
                    return Response({"error": "User not found"}, status=status.HTTP_400_BAD_REQUEST)
            except IndexError:
                # error for split-jwt token
                return Response({"error": "Invalid jwt-token-header(split)"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Authorization header is missing"}, status=status.HTTP_400_BAD_REQUEST)
        # None means OK(same as PASS)
        return None

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
