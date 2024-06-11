import os
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import re_path

from game.consumers import GameConsumer
from user.consumers import MemberConsumer


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                [
                    re_path(
                        r"^ws/play/(?P<mode>\w+)/(?P<room_name>[^/]+)/$",
                        GameConsumer.as_asgi(),
                    ),
                    re_path(
                        r"^ws/member/login_room/$",
                        MemberConsumer.as_asgi(),
                    ),
                ]
            )
        ),
    }
)
