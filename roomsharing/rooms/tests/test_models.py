from roomsharing.rooms.models import Room


def test_room_get_absolute_url(room: Room):
    assert room.get_absolute_url() == f"/rooms/{room.slug}/"
