from django.urls import resolve
from django.urls import reverse

from roomsharing.rooms.models import Room


def test_show_room(room: Room):
    assert (
        reverse("rooms:show-room", kwargs={"room_slug": room.slug})
        == f"/rooms/{room.slug}/"
    )
    assert resolve(f"/rooms/{room.slug}/").view_name == "rooms:show-room"


def test_list_rooms():
    assert reverse("rooms:list-rooms") == "/rooms/"
    assert resolve("/rooms/").view_name == "rooms:list-rooms"


def test_room_planner():
    assert reverse("rooms:planner") == "/rooms/planner/"
    assert resolve("/rooms/planner/").view_name == "rooms:planner"


def test_get_compensations():
    assert reverse("rooms:get-compensations") == "/rooms/get-compensations/"
    assert resolve("/rooms/get-compensations/").view_name == "rooms:get-compensations"
