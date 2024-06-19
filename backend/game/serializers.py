# serializers.py
from rest_framework import serializers
from .models import Game


class GameResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ['user1', 'user2', 'user1_score', 'user2_score', 'game_type']


class NicknameSerializer(serializers.Serializer):
    nickname = serializers.CharField(read_only=True)
    realname = serializers.CharField(read_only=True)
