# serializers.py
from rest_framework import serializers
from .models import Game


class GameResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ['user1_id', 'user2_id', 'user1_score', 'user2_score', 'game_type']
