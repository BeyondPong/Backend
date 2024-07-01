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
ball_speed = 12
paddle_speed = 6


class GameConsumer(AsyncWebsocketConsumer):
    # global_data in class
    running = {}
    is_final = {}

    """
    ** constructor
    """

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
        self.running_user = False
        self.paddles = {}
        self.scores = {}

    """
    connect & disconnect method
    """

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

        current_participants = cache.get(
            f"{self.room_name}_participants", {"players": [], "spectators": []}
        )

        # game_mode에 따라 참가자 추가
        if self.mode == "TOURNAMENT":
            player_count = len(current_participants["players"])
            if player_count < 2:
                if player_count == 0:
                    self.running_user = True
                current_participants["players"].append(self.nickname)
            else:
                current_participants["spectators"].append(self.nickname)
        else:  # REMOTE
            current_participants["players"].append(self.nickname)

        # debugging
        logger.debug(f"current_participants: {current_participants}")

        # dictionary setting for variables(running, is_final)
        GameConsumer.running[self.room_name] = False
        GameConsumer.is_final[self.room_name] = False
        if self.mode == "REMOTE":
            GameConsumer.is_final[self.room_name] = True

        cache.set(f"{self.room_name}_participants", current_participants)

        await sync_to_async(manage_participants)(self.room_name, increase=True)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        if self.mode == "REMOTE" and len(current_participants["players"]) == 2:
            self.running_user = True
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_event",
                    "event_type": "start_game",
                    "data": {},
                },
            )

    async def disconnect(self, close_code):
        users = cache.get(f"{self.room_name}_participants", None)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await sync_to_async(manage_participants)(self.room_name, decrease=True)
        await sync_to_async(self.remove_participant_from_cache)()
        await self.check_end_game(users)

        if self.mode == "TOURNAMENT":
            await sync_to_async(self.remove_nickname_from_cache)()
            current_nicknames = cache.get(f"{self.room_name}_nicknames", [])
            await self.send_nickname_validation(current_nicknames)

        if self.mode == "REMOTE":
            participants = cache.get(f"{self.room_name}_participants", None)
            if (
                participants
                and len(participants["players"]) == 0
                and len(participants["spectators"]) == 0
            ):
                del GameConsumer.running[self.room_name]

    async def check_end_game(self, users):
        if (not users or len(users["players"]) == 0) or (len(users["players"]) == 1):
            return

        if self.nickname in users["players"]:  # players가 나간 경우
            opponent = next(p for p in users["players"] if p != self.nickname)
            self.scores[opponent] = 7
            if GameConsumer.running[self.room_name]:
                await self.end_game(opponent, self.nickname)
            GameConsumer.running[self.room_name] = False

        elif len(users["spectators"]) == 2:  # spectators가 1명 나간 경우
            # 남은 spectators가 winner (남은 spectators가 나가더라도 winner는 이미 여기서 정해짐)
            winner = next(
                (
                    spectator
                    for spectator in users["spectators"]
                    if spectator != self.nickname
                )
            )
            # update winner, loser in cache
            winners = cache.get(f"{self.room_name}_winners", [])
            losers = cache.get(f"{self.room_name}_losers", [])
            winners.append(winner)
            losers.append(self.nickname)
            cache.set(f"{self.room_name}_winners", winners)
            cache.set(f"{self.room_name}_losers", losers)

    def remove_nickname_from_cache(self):
        logger.debug(
            f"==============remove_nickname_from_cache: {self.nickname}=============="
        )
        current_nicknames = cache.get(f"{self.room_name}_nicknames", [])
        logger.debug(f"before remove current_NICK: {current_nicknames}")
        nickname = self.scope["user"].nickname
        current_nicknames = [n for n in current_nicknames if n[1] != nickname]
        cache.set(f"{self.room_name}_nicknames", current_nicknames)
        logger.debug(f"after remove current_NICK: {current_nicknames}")

    def remove_participant_from_cache(self):
        logger.debug(
            f"==============remove_participant_from_cache: {self.nickname}=============="
        )
        current_participants = cache.get(f"{self.room_name}_participants", None)
        if not current_participants:
            return

        logger.debug(f"before remove current_participants: {current_participants}")
        # nickname = self.scope["user"].nickname

        # players 또는 spectators에서 self.nickname 삭제
        current_participants["players"] = [
            p for p in current_participants["players"] if p != self.nickname
        ]
        current_participants["spectators"] = [
            p for p in current_participants["spectators"] if p != self.nickname
        ]

        cache.set(f"{self.room_name}_participants", current_participants)

        logger.debug(
            f"Updated participants in {self.room_name}: {current_participants}"
        )

    """
    ** receive method (from frontend-action)
    """

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["type"]

        if action == "check_nickname":
            if self.mode == "TOURNAMENT":
                tournament_nickname = data["nickname"]
                nickname = self.nickname
                await self.check_nickname(tournament_nickname, nickname)

        elif action == "set_board":
            # 창 크기 정보 캐시에서 가져오거나 초기화
            windows = cache.get(
                f"{self.room_name}_windows", {"width": [], "height": []}
            )
            game_width = data["width"]
            game_height = data["height"]
            # 현재 게임 창 크기 추가
            windows["width"].append(game_width)
            windows["height"].append(game_height)
            cache.set(f"{self.room_name}_windows", windows)

        elif action == "start_game":
            windows = cache.get(f"{self.room_name}_windows")
            game_width = min(windows["width"])
            game_height = min(windows["height"])
            await self.game_settings(game_width, game_height)
            if self.running_user:
                asyncio.create_task(self.start_ball_movement())

        elif action == "move_paddle":
            if not GameConsumer.running[self.room_name]:
                return
            paddle_owner = data["paddle"]
            direction = data["direction"]
            await self.move_paddle(paddle_owner, direction)
            await self.send_paddle_position()

    """
    ** action method
    """

    async def check_nickname(self, tournament_nickname, nickname):
        current_participants = cache.get(f"{self.room_name}_participants")
        current_nicknames = cache.get(f"{self.room_name}_nicknames", [])
        # delete!!!!!!!!!!!!!!!!!!
        logger.debug("==============CHECK NICKNAME==============")
        logger.debug(f"accepted tournament-nickname: {tournament_nickname}")
        logger.debug(f"before append -> current_nicknames: {current_nicknames}")
        logger.debug(f"before change -> current_participants: {current_participants}")

        if any(nick == tournament_nickname for nick, _ in current_nicknames):
            logger.debug(f"{tournament_nickname} is in nicknames!! request again!!")
            await self.send(text_data=json.dumps({"valid": False}))
            return

        if (
            nickname in current_participants["players"]
            or nickname in current_participants["spectators"]
        ):
            current_nicknames.append((tournament_nickname, nickname))
            cache.set(f"{self.room_name}_nicknames", current_nicknames)
            logger.debug(f"current_nicknames: {current_nicknames}")

        if len(current_nicknames) == 4:
            logger.debug("4명이 다 들어왔습니다!")
            GameConsumer.is_final[self.room_name] = False
            serialized_nicknames = await self.serialize_nicknames(current_nicknames)
            current_nicknames = cache.get(f"{self.room_name}_nicknames", [])
            nickname_mapping = {real: tourney for tourney, real in current_nicknames}

            if self.nickname == current_nicknames[0][1]:
                self.running_user = True
            logger.debug(f"serialized_nicknames: {serialized_nicknames}")

            current_participants = cache.get(
                f"{self.room_name}_participants", {"players": [], "spectators": []}
            )

            # Update players with tournament nicknames
            updated_players = [
                nickname_mapping.get(nickname, nickname)
                for nickname in current_participants["players"]
            ]
            # Update spectators with tournament nicknames
            updated_spectators = [
                nickname_mapping.get(nickname, nickname)
                for nickname in current_participants["spectators"]
            ]

            current_participants["players"] = updated_players
            current_participants["spectators"] = updated_spectators

            cache.set(f"{self.room_name}_participants", current_participants)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "broadcast_event",
                    "event_type": "start_game",
                    "data": {
                        "nicknames": serialized_nicknames,
                    },
                },
            )

        logger.debug("--------------after update--------------")
        logger.debug(f"accepted tournament-nickname: {tournament_nickname}")
        logger.debug(f"after append -> current_nicknames: {current_nicknames}")
        logger.debug(f"after change -> current_participants: {current_participants}")
        logger.debug("==========================================")
        self.nickname = tournament_nickname  # 토너먼트면 self.nickname까지 tournament_nickname으로 변경

        await self.send_nickname_validation(current_nicknames)

    async def game_settings(self, game_width, game_height):
        self.game_width = game_width
        self.game_height = game_height
        self.paddle_width = paddle_width
        self.paddle_height = grid
        self.max_paddle_x = self.game_width - grid - self.paddle_width

        current_participants = cache.get(f"{self.room_name}_participants")
        winners = cache.get(f"{self.room_name}_winners", [])

        # 현재 방의 상태를 in_game = True로 변경
        rooms = cache.get("rooms", {})
        logger.debug(f"Rooms: {rooms}")
        rooms_details = rooms.get(self.room_name, {})
        rooms_details["in_game"] = True
        rooms[self.room_name] = rooms_details
        cache.set("rooms", rooms)

        # player lefts room before start game
        if len(winners) == 2 and len(current_participants["players"]) < 2:
            # only in tournament-final-round
            await self.handle_pre_game_player_exit(
                current_participants["players"], winners
            )
            return
        elif len(current_participants["players"]) < 2:
            # another round
            await self.send_game_data("game_start")
            return

        # init and send game_data
        await self.init_data()
        self.scores = {nickname: 0 for nickname in current_participants["players"]}
        if self.running_user:
            GameConsumer.running[self.room_name] = True
            await self.send_game_data("game_start")

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

        current_participants = cache.get(f"{self.room_name}_participants")
        if (
            current_participants
            and len(current_participants["players"]) == 2
            and current_participants["players"][0] in self.paddles
            and current_participants["players"][1] in self.paddles
        ):
            bottom_paddle_mid = self.paddles[current_participants["players"][0]][
                "y"
            ] + (self.paddles[current_participants["players"][0]]["height"] / 2 + 10)
            top_paddle_mid = self.paddles[current_participants["players"][1]]["y"] - (
                self.paddles[current_participants["players"][1]]["height"] / 2 + 10
            )
            if ball["y"] < top_paddle_mid:
                await self.update_game_score(
                    current_participants["players"][0],
                    current_participants["players"][1],
                )
            elif ball["y"] > bottom_paddle_mid:
                await self.update_game_score(
                    current_participants["players"][1],
                    current_participants["players"][0],
                )
            # current_participants에 없는 경우에 대해 paddle_position 보내지 못하도록 if문 안에 넣음
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

        current_participants = cache.get(f"{self.room_name}_participants")
        if len(current_participants["players"]) < 2:
            return
        if current_participants["players"][1] in self.paddles:
            top_paddle = self.paddles[current_participants["players"][1]]
        else:
            top_paddle = None

        if current_participants["players"][0] in self.paddles:
            bottom_paddle = self.paddles[current_participants["players"][0]]
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
        GameConsumer.running[self.room_name] = False
        self.scores[winner] += 1

        # call end_game! and game stopped
        if self.scores[winner] >= 7:
            await self.end_game(winner, loser)
            return

        # send score
        await self.send_game_score()

        current_participants = cache.get(f"{self.room_name}_participants")
        if winner == self.paddles[current_participants["players"][0]]["nickname"]:
            self.ball_velocity = {"x": 0, "y": 5}
        else:
            self.ball_velocity = {"x": 0, "y": -5}

        # sleep and restart_game(send restart game_data)
        await asyncio.sleep(2)
        await self.init_data(flag=True)
        await self.send_game_data("game_restart")
        GameConsumer.running[self.room_name] = True

    async def end_game(self, winner, loser):
        GameConsumer.running[self.room_name] = False
        self.running_user = False
        await self.send_end_game_data(winner, loser)

        # prepare for only next_round
        if self.mode == "TOURNAMENT" and not GameConsumer.is_final[self.room_name]:
            await self.prepare_next_tournament(winner, loser)

    """
    ** util method
    """

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

    async def serialize_nicknames(self, current_nicknames):
        serialized_nicknames = []
        for nick, real in current_nicknames:
            user = await database_sync_to_async(Member.objects.get)(nickname=real)
            win_cnt = await database_sync_to_async(
                Game.objects.filter(
                    (Q(user1=user) & Q(user1_score__gt=F("user2_score")))
                    | (Q(user2=user) & Q(user2_score__gt=F("user1_score")))
                ).count
            )()
            lose_cnt = await database_sync_to_async(
                Game.objects.filter(
                    (Q(user1=user) & Q(user1_score__lt=F("user2_score")))
                    | (Q(user2=user) & Q(user2_score__lt=F("user1_score")))
                ).count
            )()
            serialized_nicknames.append(
                {
                    "nickname": nick,
                    "win_cnt": win_cnt,
                    "lose_cnt": lose_cnt,
                    "profile_img": user.profile_img,
                }
            )
        return serialized_nicknames

    async def init_data(self, flag=False, winner_setting=False):
        current_participants = cache.get(
            f"{self.room_name}_participants", {"players": [], "spectators": []}
        )
        self.ball_position = {"x": self.game_width / 2, "y": self.game_height / 2}
        if flag is False:
            self.ball_velocity = {"x": 0, "y": 5}
        if winner_setting is True:
            current_participants["players"] = cache.get(f"{self.room_name}_winners")
        if len(current_participants["players"]) < 2:
            return
        self.paddles[current_participants["players"][0]] = {
            "nickname": current_participants["players"][0],
            "x": self.game_width / 2 - self.paddle_width / 2,
            "y": self.game_height - grid * 3,
            "width": self.paddle_width,
            "height": grid,
        }
        self.paddles[current_participants["players"][1]] = {
            "nickname": current_participants["players"][1],
            "x": self.game_width / 2 - self.paddle_width / 2,
            "y": grid * 2,
            "width": self.paddle_width,
            "height": grid,
        }

    async def prepare_next_tournament(self, winner, loser):
        self.running_user = False
        current_participants = cache.get(
            f"{self.room_name}_participants", {"players": [], "spectators": []}
        )

        # update winner, loser in cache
        winners = cache.get(f"{self.room_name}_winners", [])
        losers = cache.get(f"{self.room_name}_losers", [])
        winners.append(winner)
        losers.append(loser)
        cache.set(f"{self.room_name}_winners", winners)
        cache.set(f"{self.room_name}_losers", losers)

        # round_type for next_round or final_round
        round_type = "next_round"

        if len(current_participants["spectators"]) == 2:  # 4강 2경기
            new_players = current_participants["spectators"]
            current_participants["players"] = new_players
            current_participants["spectators"] = []

            cache.set(f"{self.room_name}_participants", current_participants)

        elif len(winners) == 2:  # 파이널
            GameConsumer.is_final[self.room_name] = True
            round_type = "final_round"

            # setting for left-spectator in winner(first round)
            current_nicknames = cache.get(f"{self.room_name}_nicknames", [])
            if len(current_participants["spectators"]) == 0 and not any(
                nick == winners[0] for nick, _ in current_nicknames
            ):
                current_participants["players"] = []
                current_participants["players"].append(winner)
            else:
                current_participants["players"] = winners
            cache.set(f"{self.room_name}_participants", current_participants)

        # running_user 권한 부여 후 group_send
        new_running_user = current_participants["players"][0]
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_next_tournament",
                "event_type": round_type,
                "running_user_nickname": new_running_user,
            },
        )

    async def handle_pre_game_player_exit(self, players, winners):
        self.running_user = False
        await self.init_data(winner_setting=True)
        self.scores = {nickname: 0 for nickname in winners}
        GameConsumer.running[self.room_name] = False
        await self.send_game_data("game_start")

        # sleep 1sec and end_game
        await asyncio.sleep(1)
        winner = None
        loser = None
        # current participant will be winner
        for participant in winners:
            if participant in players:
                self.scores[participant] = 7
                winner = participant
            else:
                self.scores[participant] = 0
                loser = participant
        await self.end_game(winner, loser)

    """
    ** send to group method
    """

    async def send_nickname_validation(self, current_nicknames):
        serialized_nicknames = await self.serialize_nicknames(current_nicknames)
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

    async def send_game_data(self, event_type):
        logger.debug(f"**is_final: {GameConsumer.is_final[self.room_name]}")
        current_participants = cache.get(f"{self.room_name}_participants")
        # 결승전 직전에 플레이어 중 누가 나간 경우 바뀌어야 함
        players = current_participants["players"]
        if (
            self.mode == "TOURNAMENT"
            and GameConsumer.is_final[self.room_name] == True
            and len(players) < 2
        ):
            # player left room before only for tournament-fianl-game (another games will be checked in FE)
            players = cache.get(f"{self.room_name}_winners", [])
        # if len(players) < 2: game_data에 players만 넣기
        game_data = {
            "is_final": GameConsumer.is_final[self.room_name],
            "game_width": self.game_width,
            "game_height": self.game_height,
            "ball_position": self.ball_position,
            "ball_velocity": self.ball_velocity,
            "paddles": [paddle for paddle in self.paddles.values()],
            "players": players,
            "scores": self.scores,
        }
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_game_data",
                "event_type": event_type,
                "data": game_data,
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
                "type": "broadcast_paddle_position",
                "event_type": "paddle_position",
                "data": [paddle for paddle in self.paddles.values()],
            },
        )

    async def send_game_score(self):
        game_score = {
            "scores": self.scores,
            "ball_position": self.ball_position,
        }
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_event",
                "event_type": "update_score",
                "data": game_score,
            },
        )

    async def send_end_game_data(self, winner, loser):
        end_game_data = {
            "is_final": GameConsumer.is_final[self.room_name],
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

    """
    ** custom broadcast method (default: broadcast_event)
    """

    async def broadcast_event(self, event):
        event_type = event["event_type"]
        await self.send(
            text_data=json.dumps({"type": event_type, "data": event["data"]})
        )

    async def broadcast_paddle_position(self, event):
        paddles = event["data"]
        event_type = event["event_type"]
        # update
        for paddle in paddles:
            self.paddles[paddle["nickname"]] = paddle
        # send
        await self.send(
            text_data=json.dumps({"type": event_type, "data": event["data"]})
        )

    async def broadcast_game_data(self, event):
        event_type = event["event_type"]
        data = event["data"]
        # update
        self.ball_position = data["ball_position"]
        self.ball_velocity = data["ball_velocity"]
        self.paddles = {paddle["nickname"]: paddle for paddle in data["paddles"]}
        self.scores = data["scores"]
        # send
        await self.send(
            text_data=json.dumps({"type": event_type, "data": event["data"]})
        )

    # async def broadcast_score(self, event):
    #     event_type = event["event_type"]
    #     data = event["data"]
    #     # update
    #     self.scores = data["scores"]
    #     self.ball_position = data["ball_position"]
    #     # send
    #     await self.send(
    #         text_data=json.dumps({"type": event_type, "data": event["data"]})
    #     )

    async def broadcast_next_tournament(self, event):
        event_type = event["event_type"]
        running_user_nickname = event["running_user_nickname"]
        if self.nickname == running_user_nickname:
            self.running_user = True
        else:
            self.running_user = False
        await self.send(text_data=json.dumps({"type": event_type}))

    """
    ** coroutine method
    """

    async def start_ball_movement(self):
        while GameConsumer.running[self.room_name]:
            await self.update_ball_position()
            await self.send_ball_position()
            await asyncio.sleep(0.01667)  # 60 FPS
