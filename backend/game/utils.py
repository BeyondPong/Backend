import logging
import secrets
import redis

logger = logging.getLogger(__name__)
# Redis 연결 설정
redis_client = redis.Redis(host="redis", port=6379, db=0)


def generate_room_name():

    rooms = redis_client.keys("room_*")
    for room_key in rooms:
        count = int(redis_client.get(room_key))
        logger.debug(f"count is {count}")
        if count < 2:
            room_name = room_key.decode("utf-8").split("_")[1]
            logger.debug(f"Room {room_name} incremented to {count + 1} participants.")
            return room_name

    new_room_name = secrets.token_urlsafe(8)
    redis_client.set(f"room_{new_room_name}", 1)  # 참가자가 1명인 새로운 방 생성
    logger.debug(f"New room created: {new_room_name} with 1 participant.")
    return new_room_name
