from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.test import TestCase
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.rooms.services import filter_rooms
from roomsharing.rooms.services import get_weekly_bookings
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.utils.models import BookingStatus


class GetWeeklyBookingsTest(TestCase):
    @patch.object(Booking.objects, "filter")
    @patch.object(timezone, "now")
    def test_empty_weekly_bookings(self, mock_now, mock_filter):
        # Define the return values for the mock objects
        mock_now.return_value = timezone.make_aware(timezone.datetime(2024, 7, 23))
        mock_filter.return_value = Booking.objects.none()

        room = RoomFactory()
        date_string = mock_now.return_value.strftime("%Y-%m-%d")
        time_slots, weekdays = get_weekly_bookings(room.slug, date_string)

        # Check the length of returned lists
        number_of_timeslots = 32
        assert len(time_slots) == number_of_timeslots
        number_of_weekdays = 7
        assert len(weekdays) == number_of_weekdays

        # Check some sample values
        assert time_slots[0]["time"] == datetime(
            2024, 7, 22, 8, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
        )
        assert time_slots[0]["booked"] == [
            False,
            False,
            False,
            False,
            False,
            False,
            False,
        ]
        assert weekdays[0] == datetime(
            2024, 7, 22, 0, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
        )

        # Check that every slot is False (not booked)
        for slot in time_slots:
            assert all(booked is False for booked in slot["booked"])

    @patch.object(timezone, "now")
    def test_some_bookings_exist(self, mock_now):
        mock_now.return_value = timezone.make_aware(timezone.datetime(2024, 6, 5))
        room = RoomFactory()
        booking1 = BookingFactory(
            room=room,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.datetime(2024, 6, 5, 8, 0),
                timezone.datetime(2024, 6, 5, 9, 0),
            ),
        )
        booking2 = BookingFactory(
            room=room,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.datetime(2024, 6, 5, 18, 0),
                timezone.datetime(2024, 6, 5, 22, 0),
            ),
        )
        booking1.save()
        booking2.save()

        date_string = mock_now.return_value.strftime("%Y-%m-%d")
        time_slots, weekdays = get_weekly_bookings(room.slug, date_string)

        number_of_timeslots = 32
        assert len(time_slots) == number_of_timeslots
        number_of_weekdays = 7
        assert len(weekdays) == number_of_weekdays

        # Check that specific slots are booked
        assert (
            time_slots[0]["booked"][2] is True
        )  # This should be True because we booked the slot from 8:00 to 9:00
        assert (
            time_slots[10]["booked"][2] is True
        )  # This should be False because we did not book the slot
        assert (
            time_slots[20]["booked"][2] is True
        )  # This should be True because we booked the slot from 18:00 to 22:00

    @patch.object(timezone, "now")
    def test_without_date(self, mock_now):
        mock_now.return_value = timezone.make_aware(timezone.datetime(2024, 6, 5))
        date_string = None
        room = RoomFactory()
        time_slots, weekdays = get_weekly_bookings(room.slug, date_string)
        assert time_slots[0]["booked"] == [
            False,
            False,
            False,
            False,
            False,
            False,
            False,
        ]


@pytest.mark.django_db()  # Mark for db access
@pytest.mark.parametrize(
    ("room_name", "max_persons", "expected"),
    [
        ("Room", 2, ["Room1", "Room2"]),
        ("Small Room", None, ["Small Room"]),
        (None, 3, ["Room2"]),
        (None, None, ["Room1", "Room2", "Small Room"]),
    ],
)
def test_filter_rooms(room_name, max_persons, expected):
    RoomFactory.create(name="Room1", max_persons=2)
    RoomFactory.create(name="Room2", max_persons=3)
    RoomFactory.create(name="Small Room", max_persons=1)

    rooms = filter_rooms(room_name, max_persons)
    assert {room.name for room in rooms} == set(expected)
