import json

from channels.generic.websocket import AsyncWebsocketConsumer


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"game_room_{self.room_name}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)


    # async def receive(self, text_data=None, bytes_data=None):
    #    # todo 이 부분은 나중에 게임 로직 구현할때 추가예정
    #     data = json.loads(text_data)
    #     msg = data['type']
    #     print(data['type'])

        # if msg == 'paddlePosition':
        #     paddlePosition = data['type']
        #     await self.channel_layer.group_send(
        #         self.room_name,
        #         {
        #             'type': 'paddlePosition',
        #             'position': paddlePosition
        #         }
        #     )

    # async def start_game(self, event):
    #     message = event["message"]
    #     await self.send(text_data=json.dumps({"message": message}))


# class ChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
#         self.room_group_name = "chat_%s" % self.room_name
#
#         # Join room group
#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#
#         await self.accept()
#
#     async def disconnect(self, close_code):
#         # Leave room group
#         await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
#
#     # Receive message from WebSocket
#     async def receive(self, text_data):
#         text_data_json = json.loads(text_data)
#         message = text_data_json["message"]
#
#         # Send message to room group
#         await self.channel_layer.group_send(
#             self.room_group_name, {"type": "chat_message", "message": message}
#         )
#
#     # Receive message from room group
#     async def chat_message(self, event):
#         message = event["message"]
#
#         # Send message to WebSocket
#         await self.send(text_data=json.dumps({"message": message}))
