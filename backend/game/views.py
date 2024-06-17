# Create your views here.
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from game.serializers import GameResultSerializer
from .utils import generate_room_name
from django.core.cache import cache


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
        room_name = request.data.get("room_name")

        # 방 내 현재 닉네임 목록을 캐시에서 가져옴
        current_nicknames = cache.get(f"{room_name}_nicknames", set())

        # 닉네임 중복 검사
        if nickname in current_nicknames:
            # 중복되는 경우 False 반환
            return Response({"valid": False})

        # 중복되지 않는 경우, 닉네임 추가 및 캐시 업데이트
        current_nicknames.add(nickname)
        cache.set(f"{room_name}_nicknames", current_nicknames)

        # 사용 가능한 경우 True 반환
        return Response({"valid": True, "nicknames": list(current_nicknames)})
