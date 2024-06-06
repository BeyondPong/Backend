import logging
import uuid
import redis

logger = logging.getLogger(__name__)
# Redis 연결 설정
redis_client = redis.Redis(host="redis", port=6379, db=0)


def generate_room_name():
    rooms = redis_client.keys("room_*")
    for room_key in rooms:
        # count = int(redis_client.get(room_key))
        count = get_room_count(room_key)
        if count is not None and count < 2:
            redis_client.set(room_key, count + 1)
            return room_key.decode("utf-8").split("_")[1]  # UUID 전체 반환

    new_room_name = str(uuid.uuid4())
    redis_client.set(f"room_{new_room_name}", 1)  # 참가자가 1명인 새로운 방 생성
    return new_room_name


def get_room_count(room_key):
    try:
        room_count = redis_client.get(room_key.decode("utf-8"))
        if room_count is not None:
            return int(room_count)
        else:
            return None
    except ValueError:
        logger.error(f"Data type error: Key {room_key} holds non-integer value")
        return None
