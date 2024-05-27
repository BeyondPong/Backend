import json

from channels.generic.websocket import AsyncWebsocketConsumer


class UserStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.group_name = f"user_{self.user_id}"

        # 그룹에 가입
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        # 그룹에서 탈퇴
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")

        if action == "update_status":
            status = data.get("status")
            # 친구 상태 업데이트
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "status_update",
                    "status": status,
                },
            )

    async def status_update(self, event):
        status = event["status"]
        # WebSocket에 메시지 전송
        await self.send(text_data=json.dumps({"status": status}))
