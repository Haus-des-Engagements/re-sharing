from django.urls import resolve
from django.urls import reverse

from roomsharing.rooms.models import Room


def test_room_detail(room: Room):
    assert reverse("rooms:detail", kwargs={"slug": room.slug}) == f"/rooms/{room.slug}/"
    assert resolve(f"/rooms/{room.slug}/").view_name == "rooms:detail"


def test_room_list():
    assert reverse("rooms:list") == "/rooms/"
    assert resolve("/rooms/").view_name == "rooms:list"
