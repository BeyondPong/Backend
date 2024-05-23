from django.db.models import Q, F

# Create your views here.

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from game.models import Game
from user.models import Member, Friend

from user.serializers import MemberSerializer


class GetGameHistory(APIView):
    def get(self, request):
        # todo 이부분은 나중에 jwt Token에서 가져오는 방법으로 바꿀 예정
        user_id = 1
        games = Game.objects.filter(
            Q(user1_id=user_id) | Q(user2_id=user_id)
        ).order_by('-created_at')[:10]
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


class SearchUserView(APIView):
    def get(self, request):
        nickname = request.GET.get('nickname', '')
        members = Member.objects.filter(nickname__icontains=nickname)[:10]
        serializer = MemberSerializer(members, many=True, context={'request': request})
        return JsonResponse({"users:": serializer.data}, safe=False)


class AddFriendView(APIView):
    def post(self, request, user_id):
        # todo 로그인 유저로 수정
        user = Member.objects.get(id=1)
        friend_member = get_object_or_404(Member, pk=user_id)
        if user.friends.filter(Q(user=user) & Q(friend=friend_member)).exists():
            return JsonResponse({'message': '이미 친구 입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        friend = Friend(user=user, friend=friend_member)
        friend.save()
        return JsonResponse({'message': '친구가 추가 되었습니다.'}, status=status.HTTP_201_CREATED)


class GetUserInformationView(APIView):
    def get(self, request):
        user_id = 1
        user = Member.objects.get(id=user_id)
        win_cnt = Game.objects.filter(
            (Q(user1=user) & Q(user1_score__gt=F('user2_score'))) |
            (Q(user2=user) & Q(user2_score__gt=F('user1_score')))
        ).count()
        lose_cnt = Game.objects.filter(
            (Q(user1=user) & Q(user1_score__lt=F('user2_score'))) |
            (Q(user2=user) & Q(user2_score__lt=F('user1_score')))
        ).count()
        return JsonResponse({"nickname": user.nickname,
                             "profile_img": user.profile_img.url,
                             "status_msg": user.status_msg,
                             "win_cnt": win_cnt,
                             "lose_cnt": lose_cnt,
                             "language": user.language})