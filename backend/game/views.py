# Create your views here.
import secrets
import uuid

import redis
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from game.serializers import GameResultSerializer

# from .utils import generate_room_name

redis_client = redis.Redis(host="redis", port=6379, db=0)


class GameResultView(APIView):
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
    def get(self, request):
        rooms = redis_client.keys("*")
        room_found = False

        # 참여자가 1명인 방 찾기
        for room in rooms:
            if int(redis_client.get(room.decode("utf-8"))) == 1:
                room_name = room.decode("utf-8")
                redis_client.set(room_name, 2)  # 참여자 수 2로 설정
                room_found = True
                break

        if not room_found:
            room_name = str(uuid.uuid4())
            redis_client.set(room_name, 1)

        return Response({"room_name": room_name})
