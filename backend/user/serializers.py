from rest_framework import serializers
from .models import Member, Friend


class MemberSerializer(serializers.ModelSerializer):
    is_friend = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = ['nickname', 'profile_img', 'status_msg', 'language', 'is_friend']

    def get_is_friend(self, obj):
        user_id = 1
        return Friend.objects.filter(user_id=user_id).exists()

        # todo 로그인 사용자 기준으로 찾기
        # request = self.context.get('request')
        # if request and request.user.is_authenticated:
        #     return Friend.objects.filter(user=request.user, friend=obj).exists()
        # return False
