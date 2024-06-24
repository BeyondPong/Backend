import asyncio
import json
import logging
import jwt

from channels.db import database_sync_to_async
from django.core.cache import cache

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q, F

from game.models import Game
from .utils import generate_room_name, manage_participants
from login.authentication import JWTAuthentication, decode_jwt
from django.contrib.auth.models import AnonymousUser

from user.models import Member

logger = logging.getLogger(__name__)

grid = 15
paddle_width = grid * 6
ball_speed = 6
paddle_speed = 6


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # JWT 토큰 확인 및 사용자 인증
        token_key = self.scope["query_string"].decode().split("=")[1]
        self.scope["user"] = await self.get_user_from_jwt(token_key)

        if not self.scope["user"].is_authenticated:
            logger.debug("User is not authenticated")
            return

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
                    "data": {"first_user": current_participants[0]},
                },
            )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await sync_to_async(manage_participants)(self.room_name, decrease=True)
        await sync_to_async(self.remove_nickname_from_cache)()
        await sync_to_async(self.remove_participant_from_cache)()

    @database_sync_to_async
    def get_user_from_jwt(self, token_key):
        try:
            payload = decode_jwt(token_key)
            if not payload:
                return AnonymousUser()
            user = Member.objects.get(nickname=payload["nickname"])
            logger.debug(f"JWT user: {user}")
            return user
        except (jwt.ExpiredSignatureError, jwt.DecodeError, Member.DoesNotExist):
            return AnonymousUser()

    def remove_nickname_from_cache(self):
        current_nicknames = cache.get(f"{self.room_name}_nicknames", [])
        nickname = self.scope["user"].nickname
        logger.debug("nickname : %s", nickname)
        current_nicknames = [n for n in current_nicknames if n[1] != nickname]
        cache.set(f"{self.room_name}_nicknames", current_nicknames)
        logger.debug(f"Updated nicknames in {self.room_name}: {current_nicknames}")

    def remove_participant_from_cache(self):
        current_participants = cache.get(f"{self.room_name}_participants", [])
        current_participants = [p for p in current_participants if p != self.nickname]
        cache.set(f"{self.room_name}_participants", current_participants)
        logger.debug(
            f"Updated participants in {self.room_name}: {current_participants}"
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["type"]

        if action == "check_nickname":
            if self.mode == "TOURNAMENT":
                nickname = data["nickname"]
                realname = self.nickname
                await self.check_nickname(nickname, realname)

        elif action == "start_game":  # 프론트에서 보내는거, 처음 게임 시작만 반응
            # 프론트에서 window의 width, height 받음
            game_width = data["width"]
            game_height = data["height"]
            await self.game_settings(game_width, game_height)
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

    async def check_nickname(self, nickname, realname):
        participants = cache.get(f"{self.room_name}_participants", [])
        logger.debug(f"Participants: {participants}")
        current_nicknames = cache.get(f"{self.room_name}_nicknames", [])

        if any(nick == nickname for nick, _ in current_nicknames):
            await self.send(
                text_data=json.dumps({"valid": False})
            )
            return

        if realname in participants:
            current_nicknames.append((nickname, realname))
            cache.set(f"{self.room_name}_nicknames", current_nicknames)
            logger.debug(f"current_nicknames: {current_nicknames}")
        serialized_nicknames = []
        for nick, real in current_nicknames:
            user = await database_sync_to_async(Member.objects.get)(nickname=real)
            win_cnt = await database_sync_to_async(Game.objects.filter(
                (Q(user1=user) & Q(user1_score__gt=F('user2_score'))) |
                (Q(user2=user) & Q(user2_score__gt=F('user1_score')))
            ).count)()
            lose_cnt = await database_sync_to_async(Game.objects.filter(
                (Q(user1=user) & Q(user1_score__lt=F('user2_score'))) |
                (Q(user2=user) & Q(user2_score__lt=F('user1_score')))
            ).count)()
            serialized_nicknames.append({
                "nickname": nick,
                "win_cnt": win_cnt,
                "lose_cnt": lose_cnt,
                "profile_img": user.profile_img
            })

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_event",
                "event_type": "nickname_valid",
                "data": {
                    "valid": True,
                    "nicknames": serialized_nicknames,
                },
            },
        )

    async def game_settings(self, game_width, game_height):
        self.game_width = game_width
        self.game_height = game_height
        self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
        self.ball_velocity = {"x": 5, "y": 5}
        self.paddle_width = paddle_width
        self.paddle_height = grid
        self.max_paddle_x = self.game_width - 15 - self.paddle_width

        # 참가자 목록을 캐시에서 불러오기
        current_participants = cache.get(f"{self.room_name}_participants", [])

        self.paddles = []
        if len(current_participants) >= 2:
            self.paddles.append(
                {
                    "nickname": current_participants[0],
                    "x": self.game_width / 2 - self.paddle_width / 2,
                    "y": self.game_height - grid * 3,
                    "width": self.paddle_width,
                    "height": grid,
                }
            )
            self.paddles.append(
                {
                    "nickname": current_participants[1],
                    "x": self.game_width / 2 - self.paddle_width / 2,
                    "y": grid * 2,
                    "width": self.paddle_width,
                    "height": grid,
                }
            )
        self.scores = {nickname: 0 for nickname in current_participants}
        self.running = True
        self.game_ended = False

        game_data = {
            "ball_position": self.ball_position,
            "ball_velocity": self.ball_velocity,
            "paddles": [paddle for paddle in self.paddles.values()],
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
                "data": [paddle for paddle in self.paddles.values()],
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

        if current_participants[0] in self.paddles:
            top_paddle = self.paddles[current_participants[0]]
        else:
            top_paddle = None

        if current_participants[1] in self.paddles:
            bottom_paddle = self.paddles[current_participants[1]]
        else:
            bottom_paddle = None

        if top_paddle and (
            ball["y"] <= top_paddle["y"] + top_paddle["height"]
            and ball["x"] + grid > top_paddle["x"]
            and ball["x"] < top_paddle["x"] + top_paddle["width"]
        ):
            ball_velocity["y"] *= -1
            hit_pos = (ball["x"] - top_paddle["x"]) / top_paddle["width"]
            ball_velocity["x"] = (hit_pos - 0.5) * 2 * ball_speed

        if bottom_paddle and (
            ball["y"] + grid >= bottom_paddle["y"]
            and ball["x"] + grid > bottom_paddle["x"]
            and ball["x"] < bottom_paddle["x"] + bottom_paddle["width"]
        ):
            ball_velocity["y"] *= -1
            hit_pos = (ball["x"] - bottom_paddle["x"]) / bottom_paddle["width"]
            ball_velocity["x"] = (hit_pos - 0.5) * 2 * ball_speed

    async def update_game_score(self, player):
        for score in self.scores:
            if score["nickname"] == player:
                score["score"] += 1
            if self.scores[player] >= 7:  # 게임 종료 조건
                self.running = False
                self.game_ended = True
                await self.end_game(player)
                return  # 점수 업데이트 후 나머지 로직은 실행하지 않음

        self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
        self.ball_velocity = {"x": ball_speed, "y": ball_speed}

        for paddle in self.paddles:
            paddle["x"] = self.game_width / 2 - self.paddle_width / 2
            if paddle["nickname"] == self.paddles[0]["nickname"]:
                paddle["y"] = self.game_height - grid * 3  # 하단 패들 초기 위치
            else:
                paddle["y"] = grid * 2  # 상단 패들 초기 위치
        game_score = {
            "scores": self.scores,
            "ball_position": self.ball_position,
            "ball_velocity": self.ball_velocity,
            "paddles": self.paddles,
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
            await asyncio.sleep(0.01667)  # 60 FPS
