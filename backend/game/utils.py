import logging
import secrets
from django.core.cache import cache


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
