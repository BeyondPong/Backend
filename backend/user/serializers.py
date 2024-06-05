from rest_framework import serializers
from .models import Member, Friend


class MemberSearchSerializer(serializers.ModelSerializer):
    is_friend = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = ['id', 'nickname', 'profile_img', 'status_msg', 'language', 'is_friend']

    def get_is_friend(self, obj):
        user_id = 1
        return Friend.objects.filter(user_id=user_id, friend=obj).exists()

        # todo 로그인 사용자 기준으로 찾기
        # request = self.context.get('request')
        # if request and request.user.is_authenticated:
        #     return Friend.objects.filter(user=request.user, friend=obj).exists()
        # return False


class MemberInfoSerializer(serializers.ModelSerializer):
    win_cnt = serializers.IntegerField()
    lose_cnt = serializers.IntegerField()

    class Meta:
        model = Member
        fields = ['nickname', 'profile_img', 'status_msg', 'win_cnt', 'lose_cnt', 'language']


class ImageUploadSerializer(serializers.Serializer):
    profile_img = serializers.IntegerField(required=False, allow_null=False)

    class Meta:
        model = Member
        fields = ['profile_img']


class StatusMsgSerializer(serializers.ModelSerializer):
    status_msg = serializers.CharField(required=True, allow_null=False)

    class Meta:
        model = Member
        fields = ['status_msg']


class LanguageSerializer(serializers.ModelSerializer):
    language = serializers.CharField(required=True, allow_null=False)

    class Meta:
        model = Member
        fields = ['language']