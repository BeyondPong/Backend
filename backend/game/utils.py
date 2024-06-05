import logging
import uuid
import redis

# logger = logging.getLogger(__name__)
# Redis 연결 설정
redis_client = redis.Redis(host="redis", port=6379, db=0)


def generate_room_name():

    rooms = redis_client.keys("room_*")
    for room_key in rooms:
        count = int(redis_client.get(room_key))
        if count < 2:
            return room_key.decode("utf-8").split("_")[1]  # UUID 전체 반환

    new_room_name = str(uuid.uuid4())
    redis_client.set(f"room_{new_room_name}", 1)  # 참가자가 1명인 새로운 방 생성
    return new_room_name
