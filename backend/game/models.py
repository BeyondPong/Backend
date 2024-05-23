from django.core.validators import MinValueValidator
from django.db import models
from rest_framework.exceptions import ValidationError

from user.models import Member


# Create your models here.
class Game(models.Model):
    GAME_TYPE_CHOICES = [
        ("LOCAL", "Local Game"),
        ("REMOTE", "Remote Game"),
        ("TOURNAMENT", "Tournament Game"),
    ]

    user1 = models.ForeignKey(
        Member,
        related_name="games_as_user1",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    user2 = models.ForeignKey(
        Member,
        related_name="games_as_user2",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    user1_score = models.IntegerField(null=False, validators=[MinValueValidator(0)])
    user2_score = models.IntegerField(null=False, validators=[MinValueValidator(0)])
    game_type = models.CharField(null=False, max_length=10, choices=GAME_TYPE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.user1_id == self.user2_id:
            raise ValidationError("User and friend cannot be the same person.")
        if self.user1_score == self.user2_score:
            raise ValidationError("Score cannot be the same.")

    def save(self, *args, **kwargs):
        self.clean()
        super(Game, self).save(*args, **kwargs)

    def __str__(self):
        return f"user1 : {self.user1_id}, user2: {self.user2_id} type : {self.game_type} {self.created_at}"