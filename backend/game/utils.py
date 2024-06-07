import logging
import secrets
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
    if not rooms or all(rooms[r] == 2 for r in rooms):
        new_room_name = secrets.token_urlsafe(8)
        rooms[new_room_name] = 0
        cache.set("rooms", rooms)
        return new_room_name
    else:
        return next(r for r in rooms if rooms[r] < 2)


def manage_participants(room_name, increase=False, decrease=False):
    rooms = cache.get("rooms", {})
    if increase:
        rooms[room_name] += 1
    if decrease:
        rooms[room_name] -= 1
        if rooms[room_name] <= 0:
            del rooms[room_name]
    cache.set("rooms", rooms)
    return rooms.get(room_name, 0)
