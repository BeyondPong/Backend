from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class CustomUser(AbstractUser):
	nickname = models.CharField(max_length=20, null=True, blank=True)
	profile_img = models.ImageField(upload_to='profile_images/', null=True, blank=True)
	status_msg = models.CharField(max_length=40, null=True, blank=True)
	# language = models.CharField(max_length=20, null=True, blank=True)

	def __str__(self):
		return self.nickname if self.nickname else self.username
	
class Friend(models.Model):
	user = models.ForeignKey(CustomUser, related_name='friends', on_delete=models.CASCADE)
	friend = models.ForeignKey(CustomUser, related_name='friend_of', on_delete=models.CASCADE)
	
	class Meta:
		unique_together = ('user', 'friend')

	def __str__(self):
		return f"{self.user} is friends with {self.friend}"