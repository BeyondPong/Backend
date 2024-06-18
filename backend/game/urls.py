from django.urls import path
from . import views
from .views import GetRoomNameView, CheckNicknameView

urlpatterns = [
    path("result/", views.GameResultView.as_view(), name="game_result"),
    path("room/", views.GetRoomNameView.as_view(), name="room"),
    path("<str:nickname>/", CheckNicknameView.as_view(), name="check_nickname"),
]
