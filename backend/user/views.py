from django.db.models import Q
from django.shortcuts import render

# Create your views here.

from django.http import JsonResponse
from rest_framework import status
from rest_framework.views import APIView

from game.models import Game


class GetGameHistory(APIView):
    def get(self, request):
        # todo 이부분은 나중에 jwt Token에서 가져오는 방법으로 바꿀 예정
        user_id = request.user.id
        games = Game.objects.filter(
            Q(user1_id=user_id) | Q(user2_id=user_id)
        ).order_by('-created_at')
        histories = self.create_game_histories_json(user_id, games)
        return JsonResponse({"histories": histories}, status=status.HTTP_200_OK)

    def create_game_histories_json(self, user_id, games):
        histories = []
        for game in games:
            if game.user1_id.id == user_id:
                opponent = game.user2_id.nickname
                my_score = game.user1_score
                opponent_score = game.user2_score
            else:
                opponent = game.user1_id.nickname
                my_score = game.user2_score
                opponent_score = game.user1_score

            if my_score > opponent_score:
                result = "Win"
            else:
                result = "Lose"

            histories.append({
                "date": game.created_at.strftime("%Y-%m-%d"),
                "opponent": opponent,
                "match_score": f"{my_score}:{opponent_score}",
                "result": result
            })
        return histories
