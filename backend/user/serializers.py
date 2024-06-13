from django_redis import get_redis_connection
from rest_framework import serializers
from .models import Member, Friend


class MemberSearchSerializer(serializers.ModelSerializer):
    is_friend = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = ['id', 'nickname', 'profile_img', 'status_msg', 'language', 'is_friend']

    def get_is_friend(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Friend.objects.filter(user=request.user, friend=obj).exists()
        return False


class MemberInfoSerializer(serializers.ModelSerializer):
    win_cnt = serializers.IntegerField()
    lose_cnt = serializers.IntegerField()

    class Meta:
        model = Member
        fields = ['nickname', 'profile_img', 'status_msg', 'win_cnt', 'lose_cnt', 'language']


class ImageUploadSerializer(serializers.Serializer):
    profile_img = serializers.IntegerField(required=True, allow_null=False)

    class Meta:
        model = Member
        fields = ['profile_img']


class StatusMsgSerializer(serializers.ModelSerializer):
    status_msg = serializers.CharField(required=True, allow_null=False)

    class Meta:
        model = Member
        fields = ['status_msg']


class LanguageSerializer(serializers.ModelSerializer):
    LANGUAGE_CODE = Member.LANGUAGE_CODE

    language = serializers.ChoiceField(choices=LANGUAGE_CODE, required=True)

    class Meta:
        model = Member
        fields = ['language']


class FriendListSerializer(serializers.ModelSerializer):
    is_connected = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = ['id', 'is_connected', 'nickname', 'profile_img', 'status_msg']

    def get_is_connected(self, obj):
        redis_conn = get_redis_connection("default")
        if redis_conn.sismember("login_room_users", obj.nickname):
            return True
        else:
            return False
