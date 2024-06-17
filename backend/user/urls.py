from django.urls import path

from . import views

urlpatterns = [
    path('history/', views.GetGameHistory.as_view(), name='game_history'),
    path('search/', views.SearchUserView.as_view(), name='search_user'),
    path('search/<int:user_id>/', views.AddFriendView.as_view(), name='add_user'),
    path('information/', views.GetUserInformationView.as_view(), name='information'),
    path('information/photo/', views.PatchUserPhotoView.as_view(), name='information_photo'),
    path('information/message/', views.PatchUserStatusMsgView.as_view(), name='information_message'),
    path('friends/<int:user_id>/', views.FriendDeleteAPIView.as_view(), name='delete_friend'),
    path('language/', views.PatchLanguageAPIView.as_view(), name='patch_language'),
    path('friends/', views.GetFriendListView.as_view(), name='friend_list'),
    path('friends/<int:user_id>/', views.DeleteFriendAPIView.as_view(), name='delete_friend'),
    path('withdrawal/', views.WithdrawalUserView.as_view(), name='withdrawal_user'),
]
