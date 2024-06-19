import asyncio
import json
import logging
from django.core.cache import cache

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from .utils import generate_room_name, manage_participants

logger = logging.getLogger(__name__)

grid = 15
paddle_width = grid * 6
ball_speed = 6
paddle_speed = 6


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.mode = self.scope["url_route"]["kwargs"]["mode"]
        self.nickname = self.scope["url_route"]["kwargs"]["nickname"]
        self.room_name = await sync_to_async(generate_room_name)(self.mode)
        self.room_group_name = f"game_room_{self.room_name}"

        current_participants = cache.get(f"{self.room_name}_participants", [])
        if not current_participants:
            cache.set(
                f"{self.room_name}_participants", current_participants, timeout=3600
            )
        # 참가자 추가
        current_participants.append(self.nickname)
        cache.set(f"{self.room_name}_participants", current_participants)

        await sync_to_async(manage_participants)(self.room_name, increase=True)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        max_participants = 2 if self.mode == "REMOTE" else 4

        if len(current_participants) == max_participants:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_event",
                    "event_type": "start_game",
                    "data": {
                        "message": f"{max_participants} players are online, starting game."
                    },
                },
            )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await sync_to_async(manage_participants)(self.room_name, decrease=True)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["type"]

        if action == "start_game":
            # 프론트에서 window의 width, height 받음
            game_width = 100
            game_height = 100
            await self.game_settings(game_width, game_height)
            # await self.start_ball_movement()
            asyncio.create_task(self.start_ball_movement())

        elif action == "move_ball":
            self.update_ball_position()
            await self.send_ball_position()

        elif action == "move_paddle":
            paddle = data["paddle"]
            direction = data["direction"]
            await self.move_paddle(paddle, direction)
            await self.send_paddle_position()

        elif action == "update_score":
            player_id = data["player_id"]
            await self.update_game_score(player_id)

        elif action == "end_game":
            await self.end_game()

    async def game_settings(self, game_width, game_height):
        self.game_width = game_width
        self.game_height = game_height
        self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
        self.ball_velocity = {"x": 5, "y": 5}
        self.paddle_width = paddle_width
        self.paddle_height = grid
        self.max_paddle_x = self.game_width - 15 - self.paddle_width

        # 참가자 목록을 캐시에서 불러오기
        current_paricipants = cache.get(f"{self.room_name}_participants", [])

        self.paddles = []
        if len(current_paricipants) >= 2:
            self.paddles.append(
                {
                    "nickname": current_paricipants[0],
                    "x": self.game_width / 2 - self.paddle_width / 2,
                    "y": grid * 2,
                    "width": self.paddle_width,
                    "height": grid,
                }
            )
            self.paddles.append(
                {
                    "nickname": current_paricipants[1],
                    "x": self.game_width / 2 - self.paddle_width / 2,
                    "y": self.game_height - grid * 3,
                    "width": self.paddle_width,
                    "height": grid,
                }
            )
        self.scores = {nickname: 0 for nickname in current_paricipants}
        self.running = True
        self.game_ended = False

        game_data = {
            "ball_position": self.ball_position,
            "ball_velocity": self.ball_velocity,
            "paddles": self.paddles,
            "scores": self.scores,
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "broadcast_event", "event_type": "game_start", "data": game_data},
        )

    async def send_ball_position(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_event",
                "event_type": "ball_position",
                "data": self.ball_position,
            },
        )

    async def send_paddle_position(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_event",
                "event_type": "paddle_position",
                "data": self.paddles,
            },
        )

    async def update_ball_position(self):
        ball = self.ball_position
        ball_velocity = self.ball_velocity
        # 현재 속도에 따른 공 위치 업데이트
        ball["x"] += ball_velocity["x"]
        ball["y"] += ball_velocity["y"]

        current_participants = cache.get(f"{self.room_name}_participants", [])

        if ball["x"] < grid:
            ball["x"] = grid
            ball_velocity["x"] *= -1
        elif ball["x"] + grid > self.game_width - grid:
            ball["x"] = self.game_width - grid * 2
            ball_velocity["x"] *= -1

        if ball["y"] < 0:
            await self.update_game_score(current_participants[1])
        elif ball["y"] > self.game_height:
            await self.update_game_score(current_participants[0])

        await self.check_paddle_collision()

    async def move_paddle(self, paddle, direction):
        if direction == "left":
            self.paddles[paddle]["x"] = max(
                grid, self.paddles[paddle]["x"] - paddle_speed
            )
        elif direction == "right":
            self.paddles[paddle]["x"] = min(
                self.max_paddle_x, self.paddles[paddle]["x"] + paddle_speed
            )

    async def check_paddle_collision(self):
        ball = self.ball_position
        ball_velocity = self.ball_velocity
        current_participants = cache.get(f"{self.room_name}_participants", [])

        if len(current_participants) >= 2:
            top_paddle = self.paddles[current_participants[0]]
            bottom_paddle = self.paddles[current_participants[1]]

        if (
            ball["y"] <= top_paddle["y"] + top_paddle["height"]
            and ball["x"] + grid > top_paddle["x"]
            and ball["x"] < top_paddle["x"] + top_paddle["width"]
        ):
            ball_velocity["y"] *= -1
            hit_pos = (ball["x"] - top_paddle["x"]) / top_paddle["width"]
            ball_velocity["x"] = (hit_pos - 0.5) * 2 * ball_speed

        if (
            ball["y"] + grid >= bottom_paddle["y"]
            and ball["x"] + grid > bottom_paddle["x"]
            and ball["x"] < bottom_paddle["x"] + bottom_paddle["width"]
        ):
            ball_velocity["y"] *= -1
            hit_pos = (ball["x"] - bottom_paddle["x"]) / bottom_paddle["width"]
            ball_velocity["x"] = (hit_pos - 0.5) * 2 * ball_speed

    async def update_game_score(self, player):
        self.scores[player] += 1
        if self.scores[player] >= 7:  # 게임 종료 조건
            self.running = False
            self.game_ended = True
            await self.end_game(player)
        else:
            self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
            self.ball_velocity = {"x": ball_speed, "y": ball_speed}

            game_score = {
                "scores": self.scores,
                "ball_position": self.ball_position,
                "ball_velocity": self.ball_velocity,
            }

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_event",
                    "event_type": "update_score",
                    "data": game_score,
                },
            )

    async def end_game(self, winner):
        self.running = False
        self.game_ended = True

        end_game_data = {
            "winner": winner,
            "scores": self.scores,
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_event",
                "event_type": "end_game",
                "data": end_game_data,
            },
        )

    async def broadcast_event(self, event):
        event_type = event["event_type"]
        await self.send(
            text_data=json.dumps({"type": event_type, "data": event["data"]})
        )

    async def start_ball_movement(self):
        while self.running:
            await self.update_ball_position()
            await self.send_ball_position()
            await asyncio.sleep(0.0625)  # 16 FPS
