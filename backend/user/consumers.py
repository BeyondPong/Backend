import jwt
import logging
from django.conf import settings
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, User
from django_redis import get_redis_connection

from login.authentication import JWTAuthentication

logger = logging.getLogger(__name__)
User = get_user_model()  

class MemberConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.debug("Login room WebSocket connected")
        self.room_name = "login_room"
        self.room_group_name = f"{self.room_name}"

        # JWT 토큰 확인 및 사용자 인증
        token_key = self.scope['query_string'].decode().split('=')[1]
        self.scope['user'] = await self.get_user_from_jwt(token_key)

        if not self.scope["user"].is_authenticated:
            logger.debug("User is not authenticated")
            return

        # 이미 방에 있는지 확인
        if await self.is_user_in_room(self.scope['user'].nickname):
            logger.debug("User already in Room")
            return

        # 사용자 방 그룹에 추가
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.add_user_to_room(self.scope['user'].nickname)

        logger.debug("WebSocket accepted")
        await self.accept()
        await self.send(text_data="큰방에 연결되었습니다.")

    async def disconnect(self, close_code):
        logger.debug(f"WebSocket disconnected: {close_code}")
        if self.scope["user"].is_authenticated:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )
            await self.remove_user_from_room(self.scope['user'].nickname)

    @database_sync_to_async
    def get_user_from_jwt(self, token_key):
        try:
            payload = JWTAuthentication._decode_jwt(token_key)
            if not payload:
                return AnonymousUser()
            user = User.objects.get(nickname=payload['nickname'])
            logger.debug(f"JWT user: {user}")
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, User.DoesNotExist):
            return AnonymousUser()

    @database_sync_to_async
    def is_user_in_room(self, nickname):
        redis_conn = get_redis_connection("default")
        return redis_conn.sismember(f"{self.room_group_name}_users", nickname)

    @database_sync_to_async
    def add_user_to_room(self, nickname):
        redis_conn = get_redis_connection("default")
        redis_conn.sadd(f"{self.room_group_name}_users", nickname)

    @database_sync_to_async
    def remove_user_from_room(self, nickname):
        redis_conn = get_redis_connection("default")
        redis_conn.srem(f"{self.room_group_name}_users", nickname)


    # async def receive(self, text_data):
    #     data = json.loads(text_data)
    #     status = data["status"]
    #
    #     # 상태 업데이트 메시지 전송
    #     await self.channel_layer.group_send(
    #         self.user_group_name,
    #         {
    #             "type": "user_status",
    #             "status": status,
    #         },
    #     )
    #
    # async def user_status(self, event):
    #     status = event["status"]
    #
    #     # WebSocket을 통해 클라이언트에 메시지 전송
    #     await self.send(text_data=json.dumps({"status": status}))
