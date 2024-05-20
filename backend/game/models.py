from django.db import models

from user.models import Member


# Create your models here.
class Game(models.Model):
    GAME_TYPE_CHOICES = [
        ("TYPE1", "Local Game"),
        ("TYPE2", "Multi Game"),
    ]

    user_id1 = models.ForeignKey(
        Member,
        related_name="games_as_user1",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    user_id2 = models.ForeignKey(
        Member,
        related_name="games_as_user2",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    user1_score = models.IntegerField(default=0)
    user2_score = models.IntegerField(default=0)
    game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
