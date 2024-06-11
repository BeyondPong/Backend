import logging
import secrets
from django.core.cache import cache

logger = logging.getLogger(__name__)


def generate_room_name(mode):
    max_participants = 2 if mode == "REMOTE" else 4
    rooms = cache.get("rooms", {})

    # 각 방에 대한 정보에 모드도 포함(count는 현재 참여자 수, max는 모드에 따라 최대 참가자 수)
    if not rooms or all(rooms[r]["count"] == rooms[r]["max"] for r in rooms):
        new_room_name = secrets.token_urlsafe(8)
        rooms[new_room_name] = {"count": 0, "max": max_participants, "mode": mode}
        cache.set("rooms", rooms)
        return new_room_name
    else:
        try:
            return next(
                r
                for r in rooms
                if rooms[r]["count"] < rooms[r]["max"] and rooms[r]["mode"] == mode
            )
        except StopIteration:
            # 모든 방이 꽉 찼거나, 조건에 맞는 방이 없는 경우 새로운 방 생성
            new_room_name = secrets.token_urlsafe(8)
            rooms[new_room_name] = {"count": 0, "max": max_participants, "mode": mode}
            cache.set("rooms", rooms)
            return new_room_name


def manage_participants(room_name, increase=False, decrease=False):
    rooms = cache.get("rooms", {})
    if increase:
        rooms[room_name]["count"] += 1
    if decrease:
        rooms[room_name]["count"] -= 1
        if rooms[room_name]["count"] <= 0:
            del rooms[room_name]
    cache.set("rooms", rooms)
    return rooms.get(room_name, {}.get("count", 0))
