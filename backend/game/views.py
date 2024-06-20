# Create your views here.
import logging

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from game.serializers import GameResultSerializer, NicknameSerializer

from user.models import Member
from game.models import Game
from .utils import generate_room_name
from django.core.cache import cache


logger = logging.getLogger(__name__)

class GameResultView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_description="Game 종류 후 결과 데이터 입력 api.",
        request_body=GameResultSerializer,
        consumes=["application/json"],
    )
    def post(self, request):
        serializer = GameResultSerializer(data=request.data)
        if serializer.is_valid():
            user1_nickname = serializer.validated_data['user1']
            user2_nickname = serializer.validated_data['user2']

            user1 = get_object_or_404(Member, nickname=user1_nickname)
            user2 = get_object_or_404(Member, nickname=user2_nickname)

            game = Game(
                user1=user1,
                user2=user2,
                user1_score=serializer.validated_data['user1_score'],
                user2_score=serializer.validated_data['user2_score'],
                game_type=serializer.validated_data['game_type']
            )
            game.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetRoomNameView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mode = request.query_params.get("mode")
        room_name = generate_room_name(mode)
        return Response({"room_name": room_name})


class CheckNicknameView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        nickname = request.data.get("nickname")
        realname = request.data.get("realname")
        room_name = request.data.get("room_name")
        logger.debug(f"nickname: {nickname}, realname: {realname}, room_name: {room_name}")
        participants = cache.get(f"{room_name}_participants", None)
        logger.debug(f"participants: {participants}")
        if participants is None:
            return Response({"Message": "Room participants not found"}, status=status.HTTP_404_NOT_FOUND)

        current_nicknames = cache.get(f"{room_name}_nicknames", set())

        if any(nick == nickname for nick, _ in current_nicknames):
            return Response({"valid": False})

        if realname in participants:
            current_nicknames.add((nickname, realname))
            cache.set(f"{room_name}_nicknames", current_nicknames)

        serialized_nicknames = NicknameSerializer(
            [{"nickname": nick, "realname": real} for nick, real in current_nicknames], many=True
        ).data

        return Response({"valid": True, "nicknames": serialized_nicknames})
