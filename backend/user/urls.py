from django.urls import path

from . import views

urlpatterns = [
    path('history/', views.GetGameHistory.as_view(), name='game_history'),
]
