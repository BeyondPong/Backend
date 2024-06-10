from django.db.models import Q
from django.test import TestCase

from user.models import Member, Friend
from game.models import Game
from user.views import GetGameHistory


# Create your tests here.
class FriendDeleteTest(TestCase):
    @classmethod
    def setUp(cls):
        member1 = Member.objects.create_user(nickname="nick1", email="nick1@test.com", password="1234")
        member2 = Member.objects.create_user(nickname="nick2", email="nick2@test.com", password="1234")

        friend = Friend(user=member1, friend=member2)
        friend.save()

    def test_delete_friend(self):
        self.assertEqual(Friend.objects.count(), 1)


class GetGameHistoryTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member1 = Member.objects.create_user(nickname="nick1", email="nick1@test.com", password="1234")
        cls.member2 = Member.objects.create_user(nickname="nick2", email="nick2@test.com", password="1234")

        game1 = Game(user1=None, user2=cls.member2, user1_score=3, user2_score=4, game_type="LOCAL")
        game2 = Game(user1=cls.member1, user2=None, user1_score=5, user2_score=6, game_type="LOCAL")
        game3 = Game(user1=None, user2=cls.member1, user1_score=4, user2_score=2, game_type="LOCAL")
        game1.save()
        game2.save()
        game3.save()

    def test_create_game_histories_json(self):
        view = GetGameHistory()
        user_id = self.member1.id
        games = Game.objects.filter(
            Q(user1_id=user_id) | Q(user2_id=user_id)
        ).order_by('-created_at')[:10]

        # 메서드 호출
        histories = view.create_game_histories_json(user_id, games)

        # 검증
        self.assertIsInstance(histories, list)
        self.assertEqual(len(histories), 2)
        self.assertEqual(histories[0]['opponent'], "Unknown")
        self.assertEqual(histories[1]['opponent'], "Unknown")
