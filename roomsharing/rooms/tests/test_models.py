from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from psycopg.types.range import Range

from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.rooms.models import Room
from roomsharing.rooms.tests.factories import RoomFactory


def test_room_get_absolute_url(room: Room):
    assert room.get_absolute_url() == f"/rooms/{room.slug}/"


class TestRoomIsBooked(TestCase):
    def setUp(self):
        self.room = RoomFactory()
        self.now = timezone.now()

    def test_is_booked_when_room_is_booked(self):
        BookingFactory(
            room=self.room,
            timespan=Range(
                self.now + timedelta(hours=1), self.now + timedelta(hours=2)
            ),
        )

        is_booked = self.room.is_booked(
            Range(
                self.now + timedelta(hours=1, minutes=30), self.now + timedelta(hours=2)
            )
        )

        assert is_booked is True

    def test_is_booked_when_room_is_not_booked(self):
        BookingFactory(
            room=self.room,
            timespan=Range(
                self.now + timedelta(hours=3), self.now + timedelta(hours=4)
            ),
        )

        is_booked = self.room.is_booked(
            Range(self.now + timedelta(hours=1), self.now + timedelta(hours=2))
        )

        assert is_booked is False
