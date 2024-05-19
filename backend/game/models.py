from django.db import models
from user.models import CustomUser

# Create your models here.
class Game(models.Model):
	GAME_TYPE_CHOICES = [
		('TYPE1', 'Local Game'),
		('TYPE2', 'Multi Game'),
	]

	user1 = models.ForeignKey(CustomUser, related_name='games_as_user1', on_delete=models.CASCADE)
	user2 = models.ForeignKey(CustomUser, related_name='games_as_user2', on_delete=models.CASCADE)
	user1_score = models.IntegerField(default=0)
	user2_score = models.IntegerField(default=0)
	game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)

	def __str__(self):
		return f"Game {self.id}: {self.user1} vs {self.user2}"