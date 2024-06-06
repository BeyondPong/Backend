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

from .utils import generate_room_name

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
        room_name = generate_room_name()
        return Response({"room_name": room_name})
