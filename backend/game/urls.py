from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("result/", views.GameResultView.as_view(), name="game_result"),
    path("<str:room_name>/", views.room, name="room"),
]
