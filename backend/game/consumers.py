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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # connect
        self.mode = None
        self.nickname = None
        self.room_name = None
        self.room_group_name = None

        # receive
        self.game_width = None
        self.game_height = None
        self.ball_position = None
        self.ball_velocity = None
        self.paddle_width = None
        self.paddle_height = None
        self.max_paddle_x = None
        self.paddles = {}
        self.scores = {}
        self.current_participants = []
        self.running = False
        self.game_ended = False

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

        self.current_participants = cache.get(f"{self.room_name}_participants", [])

        # 참가자 추가
        self.current_participants.append(self.nickname)
        cache.set(f"{self.room_name}_participants", self.current_participants)

        await sync_to_async(manage_participants)(self.room_name, increase=True)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # todo Tournament에 대한 게임 시작 로직 추가(위치 변경)
        if self.mode == "REMOTE" and len(self.current_participants) == 2:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_event",
                    "event_type": "start_game",
                    "data": {"first_user": self.current_participants[0]},
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
        self.current_participants = [p for p in self.current_participants if p != self.nickname]
        cache.set(f"{self.room_name}_participants", self.current_participants)
        logger.debug(
            f"Updated participants in {self.room_name}: {self.current_participants}"
        )

    # done
    #       move_ball, update_score, end_game 삭제
    #       action == restart_game 로직 추가
    #       update_score에서 ball_position 초기화 했던 부분 옮기기 (restart_game)
    #       game_start가 두번 호출되는 문제 해결
    #       self.running으로 while 돌리는데 다시 게임 시작할 때 이전꺼 종료시키고 다시 새로 시작할 수 있도록 로직 추가
    #       update_game_score에서 update_score을 다 진행할 거고 여기서 winner, loser 다 보내줘야 함
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["type"]

        if action == "check_nickname":
            if self.mode == "TOURNAMENT":
                nickname = data["nickname"]
                realname = self.nickname
                await self.check_nickname(nickname, realname)

        elif action == "start_game":
            await self.game_settings(data["width"], data["height"])
            if data.get("running_user"):
                asyncio.create_task(self.start_ball_movement())

        elif action == "restart_game":
            await self.init_data()
            await self.send_game_data("game_restart")
            self.running = True
            if data.get("running_user"):
                asyncio.create_task(self.start_ball_movement())

        elif action == "move_paddle":
            logger.debug(f"move_paddle: {data['paddle']}, {self.running}")
            if not self.running:
                return
            paddle_owner = data["paddle"]
            logger.debug(f"paddle owner: {paddle_owner}")
            direction = data["direction"]
            await self.move_paddle(paddle_owner, direction)
            await self.send_paddle_position()

    async def check_nickname(self, nickname, realname):
        # todo: cache.get 필요없으면 제거
        self.current_participants = cache.get(f"{self.room_name}_participants", [])
        logger.debug(f"Participants: {self.current_participants}")
        current_nicknames = cache.get(f"{self.room_name}_nicknames", [])

        if any(nick == nickname for nick, _ in current_nicknames):
            await self.send(
                text_data=json.dumps({"valid": False})
            )
            return

        if realname in self.current_participants:
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
        self.running = True

        self.game_width = game_width
        self.game_height = game_height
        self.paddle_width = paddle_width
        self.paddle_height = grid
        self.max_paddle_x = self.game_width - 15 - self.paddle_width

        # 참가자 목록을 캐시에서 불러오기
        self.current_participants = cache.get(f"{self.room_name}_participants", [])

        # 게임 시작하기 직전에 방 나간 경우(?)
        if len(self.current_participants) < 2:
            self.running = False
            self.game_ended = True
            return

        # game_data 설정해서 보내주기
        await self.init_data()
        self.scores = {nickname: 0 for nickname in self.current_participants}
        self.game_ended = False
        await self.send_game_data("game_start")

    async def init_data(self):
        self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
        self.ball_velocity = {"x": 5, "y": 5}
        self.paddles[self.current_participants[0]] = {
            "nickname": self.current_participants[0],
            "x": self.game_width / 2 - self.paddle_width / 2,
            "y": self.game_height - grid * 3,
            "width": self.paddle_width,
            "height": grid,
        }
        self.paddles[self.current_participants[1]] = {
            "nickname": self.current_participants[1],
            "x": self.game_width / 2 - self.paddle_width / 2,
            "y": grid * 2,
            "width": self.paddle_width,
            "height": grid,
        }

    async def send_game_data(self, event_type):
        game_data = {
            "ball_position": self.ball_position,
            "ball_velocity": self.ball_velocity,
            "paddles": [paddle for paddle in self.paddles.values()],
            "scores": self.scores,
        }

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_event",
                "event_type": event_type,
                "data": game_data
            },
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

        if ball["x"] < grid:
            ball["x"] = grid
            ball_velocity["x"] *= -1
        elif ball["x"] + grid > self.game_width - grid:
            ball["x"] = self.game_width - grid * 2
            ball_velocity["x"] *= -1

        if ball["y"] < 0:
            await self.update_game_score(self.current_participants[1], self.current_participants[0])
        elif ball["y"] > self.game_height:
            await self.update_game_score(self.current_participants[0], self.current_participants[1])

        await self.check_paddle_collision()

    async def move_paddle(self, paddle_owner, direction):
        if direction == "left":
            self.paddles[paddle_owner]["x"] = max(
                grid, self.paddles[paddle_owner]["x"] - paddle_speed
            )
        elif direction == "right":
            self.paddles[paddle_owner]["x"] = min(
                self.max_paddle_x, self.paddles[paddle_owner]["x"] + paddle_speed
            )

    async def check_paddle_collision(self):
        ball = self.ball_position
        ball_velocity = self.ball_velocity

        if self.current_participants[0] in self.paddles:
            top_paddle = self.paddles[self.current_participants[0]]
        else:
            top_paddle = None

        if self.current_participants[1] in self.paddles:
            bottom_paddle = self.paddles[self.current_participants[1]]
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

    async def update_game_score(self, winner, loser):
        self.running = False
        self.scores[winner] += 1
        if self.scores[winner] >= 7:  # 게임 종료 조건(end_game 여기서만 call)
            await self.end_game(winner, loser)
        else:
            # init부분 삭제
            self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
            self.ball_velocity = {"x": ball_speed, "y": ball_speed}
            # 패들 위치

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

    async def end_game(self, winner, loser):
        self.game_ended = True

        end_game_data = {
            "winner": winner,
            "loser": loser,
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
