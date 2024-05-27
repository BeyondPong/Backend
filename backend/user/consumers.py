import json
from channels.generic.websocket import AsyncWebsocketConsumer


class MemberConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.user_group_name = f"user_{self.user_id}"

        # 그룹에 채널 추가
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # 그룹에서 채널 제거
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        status = data["status"]

        # 상태 업데이트 메시지 전송
        await self.channel_layer.group_send(
            self.user_group_name,
            {
                "type": "user_status",
                "status": status,
            },
        )

    async def user_status(self, event):
        status = event["status"]

        # WebSocket을 통해 클라이언트에 메시지 전송
        await self.send(text_data=json.dumps({"status": status}))