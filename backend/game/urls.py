from django.urls import path

from . import views

urlpatterns = [
    path('result/', views.GameResultView.as_view(), name='game_result'),
]
