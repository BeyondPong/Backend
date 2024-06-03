# Create your views here.
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from game.serializers import GameResultSerializer
from django.shortcuts import render


class GameResultView(APIView):
    parser_classes = [JSONParser]
    @swagger_auto_schema(
        operation_description="Game 종류 후 결과 데이터 입력 api.",
        request_body=GameResultSerializer,
        consumes=['application/json'],
    )
    def post(self, request):
        serializer = GameResultSerializer(data=request.data)
        if serializer.is_valid():
            # 데이터 저장
            serializer.save()
            return Response({"message": "Game result saved successfully"}, status=status.HTTP_201_CREATED)
        else:
            # 데이터 검증 실패 시 에러 응답
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def index(request):
    return render(request, "game/index.html")


def room(request, room_name):
    return render(request, "game/room.html", {"room_name": room_name})
