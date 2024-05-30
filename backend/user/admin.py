from django.contrib import admin
from .models import Member, Friend
from django.contrib.auth.models import Group

admin.site.register(Friend)
admin.site.register(Member)
admin.site.unregister(Group)