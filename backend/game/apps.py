from django.apps import AppConfig
from django.core.cache import cache
import redis


class GameConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "game"

    def ready(self):
        self.clean_up_rooms()

    def clean_up_rooms(self):
        # 모든 방과 관련된 캐시 삭제
        cache.delete_pattern("rooms*")
        cache.delete_pattern("*_nicknames")
        cache.delete_pattern("*_participants")
        cache.delete_pattern("game_room_*_participants")
        print("Cleared all game-related cache data")

        redis_client = redis.StrictRedis(host="redis", port=6379, db=0)

        # 'asgi:group:game_room_*' 패턴을 가진 키들을 삭제
        keys = redis_client.keys("asgi:group:game_room_*")
        if keys:
            redis_client.delete(*keys)
            print(f"Deleted {len(keys)} keys from Redis")
