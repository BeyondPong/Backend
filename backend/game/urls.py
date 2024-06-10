from django.urls import path
from . import views
from .views import GetRoomNameView

urlpatterns = [
    path("result/", views.GameResultView.as_view(), name="game_result"),
    path("room/", views.GetRoomNameView.as_view(), name="room"),
]
