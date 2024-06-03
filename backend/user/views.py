from django.core.files.storage import default_storage
from django.db.models import Q, F

# Create your views here.

from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, JSONParser

from game.models import Game
from user.models import Member, Friend

from user.serializers import MemberSearchSerializer, MemberInfoSerializer, ImageUploadSerializer, LanguageSerializer, \
    StatusMsgSerializer

class GetGameHistory(APIView):
    @swagger_auto_schema(operation_description="사용자의 전적 내역 조회 api.")
    def get(self, request):
        # todo 이부분은 나중에 jwt Token에서 가져오는 방법으로 바꿀 예정
        user_id = 1
        games = Game.objects.filter(
            Q(user1_id=user_id) | Q(user2_id=user_id)
        ).order_by('-created_at')[:10]
        histories = self.create_game_histories_json(user_id, games)
        return Response({"histories": histories}, status=status.HTTP_200_OK)

    def create_game_histories_json(self, user_id, games):
        histories = []
        for game in games:
            if game.user1.id == user_id:
                opponent = game.user2.nickname
                my_score = game.user1_score
                opponent_score = game.user2_score
            else:
                opponent = game.user1.nickname
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
    @swagger_auto_schema(operation_description="유저 검색 결과 조회 api.")
    def get(self, request):
        nickname = request.GET.get('nickname', '')
        # todo 로그인 유저로 수정
        user_id = 1
        members = Member.objects.filter(nickname__icontains=nickname).exclude(id=user_id)[:10]
        serializer = MemberSearchSerializer(members, many=True, context={'request': request})
        return Response({"users": serializer.data})


class AddFriendView(APIView):
    @swagger_auto_schema(operation_description="친구 추가 api")
    def post(self, request, user_id):
        # todo 로그인 유저로 수정
        user = Member.objects.get(id=1)
        friend_member = get_object_or_404(Member, pk=user_id)
        if user.friends.filter(Q(user=user) & Q(friend=friend_member)).exists():
            return Response({'message': '이미 친구 입니다.'}, status=status.HTTP_400_BAD_REQUEST)

        friend = Friend(user=user, friend=friend_member)
        friend.save()
        return Response({'message': '친구가 추가 되었습니다.'}, status=status.HTTP_201_CREATED)


class GetUserInformationView(APIView):
    @swagger_auto_schema(operation_description="사용자의 프로필 정보 조회 api")
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

        user_data = {
            'nickname': user.nickname,
            'profile_img': user.profile_img,
            'status_msg': user.status_msg,
            'win_cnt': win_cnt,
            'lose_cnt': lose_cnt,
            'language': user.language,
        }

        serializer = MemberInfoSerializer(user_data, context={'request': request})
        return Response(serializer.data)


class PatchUserPhotoView(APIView):
    parser_classes = [MultiPartParser]

    @swagger_auto_schema(
        operation_description="사용자의 프로필 사진 수정 api.",
        request_body=ImageUploadSerializer,
        consumes=['multipart/form-data']
    )
    def patch(self, request):
        # todo 로그인 유저로 수정
        user_id = 1
        member = Member.objects.get(id=user_id)
        serializer = ImageUploadSerializer(data=request.data)
        if serializer.is_valid():
            if member.profile_img:
                if default_storage.exists(member.profile_img.name):
                    default_storage.delete(member.profile_img.name)
            profile_img = serializer.validated_data['image']
            member.profile_img = profile_img
            member.save()
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PatchUserStatusMsgView(APIView):
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_description="사용자의 상태 메세지 수정 api.",
        request_body=StatusMsgSerializer,
        consumes=['application/json']
    )
    def patch(self, request):
        # todo 로그인 유저로 수정
        user_id = 1
        member = Member.objects.get(id=user_id)
        serializer = StatusMsgSerializer(data=request.data)
        if serializer.is_valid():
            status_msg = serializer.validated_data['status_msg']
            member.status_msg = status_msg
            member.save()
            return Response({'message': 'StatusMsg change successfully'}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FriendDeleteAPIView(APIView):
    @swagger_auto_schema(operation_description="친구 삭제 api(user_id 는 친구의 id).")
    def delete(self, request, user_id):
        # todo 사용자 정보로 수정
        user = Member.objects.get(id=1)
        friend = get_object_or_404(Friend, user=user, friend_id=user_id)
        friend.delete()
        return Response({'message': 'Friend deleted successfully.'}, status=200)


class PatchLanguageAPIView(APIView):
    parser_classes = [JSONParser]

    @swagger_auto_schema(
        operation_description="사용자의 언어 수정 api",
        request_body=LanguageSerializer,
        consumes=['application/json']
    )
    def patch(self, request):
        # todo 로그인 유저로 수정
        user_id = 1
        member = Member.objects.get(id=user_id)
        serializer = LanguageSerializer(data=request.data)
        if serializer.is_valid():
            member.language = serializer.validated_data['language']
            member.save()
            return Response({'message': 'Language changed successfully.'}, status=200)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
