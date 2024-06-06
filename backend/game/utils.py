import logging
import uuid
from django.core.cache import cache

logger = logging.getLogger(__name__)


def list_rooms():
    rooms = cache.get("rooms", {})
    return rooms


def print_rooms():
    rooms = list_rooms()
    for room_name, count in rooms.items():
        logger.debug(f"Room: {room_name}, Participants: {count}")


def generate_room_name():
    rooms = cache.get("rooms", {})
    print_rooms()
    for room_name, count in rooms.items():
        if count == 1:
            rooms[room_name] = 2
            cache.set("rooms", rooms)
            return room_name

    new_room_name = str(uuid.uuid4())
    rooms[new_room_name] = 1
    cache.set("rooms", rooms)
    return new_room_name


def manage_participants(room_name, increase=None, query=False):
    rooms = cache.get("rooms", {})
    if query:
        return rooms.get(room_name, 0)

    if room_name in rooms:
        if increase:
            rooms[room_name] = rooms.get(room_name, 0) + 1
        else:
            if rooms[room_name] > 1:
                rooms[room_name] -= 1
            else:
                del rooms[room_name]  # 마지막 사용자가 나가면 방 삭제
    else:
        if increase:
            rooms[room_name] = 1  # 새 방 생성
    cache.set("rooms", rooms)
    return rooms.get(room_name, 0)
