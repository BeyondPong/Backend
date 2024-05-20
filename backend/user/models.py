from django.db import models
from django.forms import ValidationError


# Create your models here.
class Member(models.Model):
    LANGUAGE_CODE = [
        ("en", "English"),
        ("ko", "Korean"),
        ("jp", "Japanese"),
    ]
    nickname = models.CharField(max_length=20, null=False, blank=False)
    profile_img = models.ImageField(upload_to="profile_images/", null=True, blank=True)
    status_msg = models.CharField(max_length=40, null=True, blank=True)
    language = models.CharField(max_length=2, choices=LANGUAGE_CODE)

    def __str__(self):
        return self.nickname


class Friend(models.Model):
    user = models.ForeignKey(Member, related_name="friends", on_delete=models.CASCADE)
    friend = models.ForeignKey(
        Member, related_name="friend_of", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("user", "friend")

    def clean(self):
        if self.user == self.friend:
            raise ValidationError("User and friend cannot be the same person.")

    def save(self, *args, **kwargs):
        self.clean()
        super(Friend, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} is friends with {self.friend}"
