import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .utils import generate_room_name, manage_participants

logger = logging.getLogger(__name__)


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # initial_data = await self.receive_json()
        # nickname = initial_data("nickname")

        self.room_name = await sync_to_async(generate_room_name)()
        self.room_group_name = f"game_room_{self.room_name}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        participants = await sync_to_async(manage_participants)(
            self.room_name, increase=True
        )

        if participants == 2:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "start_game",
                    "message": "Two players are now connected in the room.",
                },
            )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await sync_to_async(manage_participants)(self.room_name, decrease=True)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["action"]

        if action == "start_game":
            # 프론트에서 window의 width, height 받음
            game_width = data["width"]
            game_height = data["height"]
            self.update_game_settings(game_width, game_height)

        if action == "move_paddle":
            paddle_id = data["paddle_id"]
            new_position = data["position"]
            # 게임 룰에 따라 위치를 조정하거나, 유효성 검사를 수행할 수 있습니다.
            # 게임 시작할 때, 프론트 쪽에서 게임 시작 시점의 가로 길이를 보내준다.
            updated_x_position = self.update_paddle_position(paddle_id, new_position)

            # 변경된 패들 위치를 모든 클라이언트에게 브로드캐스트
            await self.channel_layer.group_send(
                self.room_group_name,  # 이는 연결된 모든 클라이언트 그룹을 가리킵니다.
                {
                    "type": "paddle_position",
                    "paddle_id": paddle_id,
                    "position": updated_x_position,
                },
            )
        if action == "update_score":
            player_id = data["player_id"]
            score = data["score"]
            self.update_score(player_id, score)

    async def receive_json(self, **kwargs):
        # 클라이언트로부터 JSON 메시지 받기
        text_data = await self.receive()
        return json.loads(text_data)

    # async def manage_participants(self, room_name, increase=True):
    #     key = f"room_{room_name}"
    #     current_count = int(redis_client.get(key) or 0)
    #     if increase:
    #         redis_client.set(key, current_count + 1)
    #     else:
    #         if current_count > 0:
    #             redis_client.set(key, current_count - 1)
    #         if current_count == 1:
    #             redis_client.delete(key)  # 마지막 사용자가 나가면 키 삭제

    async def start_game(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"message": message}))

    async def send_message_to_group(self, event):
        message = event["message"]
        await self.send(
            text_data=json.dumps(
                {
                    "message": message,
                }
            )
        )

    async def update_score(self, player_id, score):
        if self.room_name in GameConsumer.room_score:
            GameConsumer.room_score[self.room_name][player_id] = score

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_score",
                "score": GameConsumer.room_score[self.room_name],
            },
        )

    async def broadcast_score(self, event):
        scores = event["scores"]
        await self.send(
            text_data=json.dumps({"action": "update_score", "scores": scores})
        )

    async def paddle_position(self, event):
        # 클라이언트로 변경된 패들 위치 정보를 보냅니다.
        await self.send(
            text_data=json.dumps(
                {
                    "action": "update_paddle",
                    "paddle_id": event["paddle_id"],
                    "position": event["position"],
                }
            )
        )

    async def update_game_settings(self, game_width, game_height):
        self.game_width = game_width
        self.game_height = game_height
        self.paddle_width = 100  # 일단 백엔드에서 패들의 너비를 100px로 설정

        # 모든 패들의 초기 위치를 중앙으로 설정
        initial_paddle_x = (self.game_width - self.paddle_width) / 2
        self.paddle_positions = {
            "player1": initial_paddle_x,
            "player2": initial_paddle_x,
        }

    async def update_paddle_position(self, paddle_id, position_x):
        max_x = self.game_width - self.paddle_width
        min_x = 0
        new_position_x = max(min_x, min(max_x, position_x))
        self.paddle_positions[f"{paddle_id}_x"] = new_position_x
        return new_position_x
