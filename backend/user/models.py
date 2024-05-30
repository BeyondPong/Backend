from django.db import models
from django.forms import ValidationError
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class MemberManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, nickname, password=None, **extra_fields):
        if not email:
            raise ValueError('must have user email')
        if not nickname:
            raise ValueError('must have nickname')
        user = self.model(
            email=self.normalize_email(email),
            nickname=nickname,
            **extra_fields
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, nickname, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_admin', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, nickname, password, **extra_fields)


class Member(AbstractBaseUser, PermissionsMixin):
    LANGUAGE_CODE = [
        ("en", "English"),
        ("ko", "Korean"),
        ("jp", "Japanese"),
    ]
    nickname = models.CharField(max_length=20, null=False, blank=False, unique=True)

    profile_img = models.ImageField(
        upload_to="profile_images/", null=True, blank=True, default="profile_images/default_img.jpg"
    )
    status_msg = models.CharField(max_length=40, null=True, blank=True)
    language = models.CharField(max_length=3, choices=LANGUAGE_CODE, default="en")

    email = models.EmailField(
        max_length=255,
        unique=True,
    )

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = MemberManager()

    USERNAME_FIELD = 'nickname'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.nickname


class Friend(models.Model):
    user = models.ForeignKey(
        Member, related_name="friends", on_delete=models.CASCADE, null=False, blank=False
    )
    friend = models.ForeignKey(
        Member, related_name="friend_of", on_delete=models.CASCADE, null=False, blank=False
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
