from django.apps import AppConfig
from django.core.cache import cache
import redis


class GameConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "game"

    def ready(self):
        self.clean_up_rooms()

    def clean_up_rooms(self):
        # Redis 클라이언트 생성
        redis_client = redis.StrictRedis(host="redis", port=6379, db=0)

        # 'asgi:group:game_room_*' 패턴을 가진 키들을 삭제
        keys = redis_client.keys("asgi:group:game_room_*")
        if keys:
            redis_client.delete(*keys)
            print(f"Deleted {len(keys)} keys from Redis")
