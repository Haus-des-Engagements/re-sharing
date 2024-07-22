from django.urls import resolve
from django.urls import reverse

from roomsharing.rooms.models import Room


def test_room_detail(room: Room):
    assert (
        reverse("rooms:show-room", kwargs={"slug": room.slug}) == f"/rooms/{room.slug}/"
    )
    assert resolve(f"/rooms/{room.slug}/").view_name == "rooms:show-room"


def test_list_rooms():
    assert reverse("rooms:list-rooms") == "/rooms/"
    assert resolve("/rooms/").view_name == "rooms:list-rooms"


def test_get_weekly_bookings(room: Room):
    assert (
        reverse("rooms:get-weekly-bookings", kwargs={"slug": room.slug})
        == f"/rooms/{room.slug}/get-weekly-bookings/"
    )
    assert (
        resolve(f"/rooms/{room.slug}/get-weekly-bookings/").view_name
        == "rooms:get-weekly-bookings"
    )
