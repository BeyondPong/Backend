import json
import logging

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

        participants = await sync_to_async(manage_participants)(
            self.room_name, increase=True
        )

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await sync_to_async(manage_participants)(self.room_name, decrease=True)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["type"]

        if action == "start_game":
            # 프론트에서 window의 width, height 받음
            game_width = data["width"]
            game_height = data["height"]
            self.game_settings(game_width, game_height)

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
        self.max_paddle_x = self.game_width - 15 - self.paddle_width
        self.paddles = {
            "player1": {"x": 30, "y": self.game_height / 2 - 50},
            "player2": {"x": self.game_width - 30, "y": self.game_height / 2 - 50},
        }
        self.scores = {"player1": 0, "player2": 0}
        self.running = True
        self.game_ended = False

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "game_start",
                "data": {
                    "ball_position": self.ball_position,
                    "ball_velocity": self.ball_velocity,
                    "paddles": self.paddles,
                    "scores": self.scores,
                },
            },
        )

    async def send_ball_position(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "ball_position",
                "data": self.ball_position,
            },
        )

    async def send_paddle_position(self):
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "paddle_position", "data": self.paddles}
        )

    async def update_ball_position(self):
        ball = self.ball_position
        ball_velocity = self.ball_velocity
        # 현재 속도에 따른 공 위치 업데이트
        ball["x"] += ball_velocity["x"]
        ball["y"] += ball_velocity["y"]

        if ball["x"] < grid:
            ball["x"] = grid
            ball_velocity["x"] *= -1
        elif ball["x"] + grid > self.game_width - grid:
            ball["x"] = self.game_width - grid * 2
            ball_velocity["x"] *= -1

        if ball["y"] < 0:
            await self.update_game_score("player2")
        elif ball["y"] > self.game_height:
            await self.update_game_score("player1")

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
        top_paddle = self.paddles["player1"]
        bottom_paddle = self.paddles["player2"]

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

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "update_score",
                    "data": {
                        "scores": self.scores,
                        "ball_position": self.ball_position,
                        "ball_velocity": self.ball_velocity,
                    },
                },
            )

    async def end_game(self, winner):
        self.running = False
        self.game_ended = True
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "end_game",
                "data": {
                    "winner": winner,
                    "scores": self.scores,
                },
            },
        )
