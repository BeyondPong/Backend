from django.urls import path

from . import views

urlpatterns = [
    path('history/', views.GetGameHistory.as_view(), name='game_history'),
    path('search/', views.SearchUserView.as_view(), name='search_user'),
    path('search/<int:user_id>/', views.AddFriendView.as_view(), name='add_user'),
    path('information/', views.GetUserInformationView.as_view(), name='information'),
]
