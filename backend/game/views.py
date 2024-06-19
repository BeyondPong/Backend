# Create your views here.
import logging

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from game.serializers import GameResultSerializer, NicknameSerializer
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
            # 데이터 저장
            serializer.save()
            return Response(
                {"message": "Game result saved successfully"},
                status=status.HTTP_201_CREATED,
            )
        else:
            # 데이터 검증 실패 시 에러 응답
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

        # 캐시에서 현재 닉네임 집합 가져오기 (튜플의 집합으로 저장)
        current_nicknames = cache.get(f"{room_name}_nicknames", set())

        # 닉네임 중복 검사
        if any(nick == nickname for nick, _ in current_nicknames):
            # 중복되는 경우 False 반환
            return Response({"valid": False})

        # 중복되지 않는 경우, 닉네임과 실명 추가 및 캐시 업데이트
        if realname in participants:
            current_nicknames.add((nickname, realname))
            cache.set(f"{room_name}_nicknames", current_nicknames)

        serialized_nicknames = NicknameSerializer(
            [{"nickname": nick, "realname": real} for nick, real in current_nicknames], many=True
        ).data

        # 사용 가능한 경우 True 반환
        return Response({"valid": True, "nicknames": serialized_nicknames})
