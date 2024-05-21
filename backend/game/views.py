# Create your views here.
from django.http import HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.views import APIView

from game.serializers import GameResultSerializer


class GameResultView(APIView):
    def post(self, request):
        serializer = GameResultSerializer(data=request.data)
        if serializer.is_valid():
            # 데이터 저장
            serializer.save()
            return JsonResponse({"message": "Game result saved successfully"}, status=status.HTTP_201_CREATED)
        else:
            # 데이터 검증 실패 시 에러 응답
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
