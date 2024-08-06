from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.test import TestCase
from django.utils import timezone

from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.rooms.services import filter_rooms
from roomsharing.rooms.services import get_access_code
from roomsharing.rooms.services import planner_table
from roomsharing.rooms.services import show_room
from roomsharing.rooms.tests.factories import AccessCodeFactory
from roomsharing.rooms.tests.factories import AccessFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.utils.models import BookingStatus


class GetWeeklyBookingsTest(TestCase):
    def test_empty_weekly_bookings(self):
        date = timezone.make_aware(timezone.datetime(2024, 7, 23))

        room = RoomFactory()
        date_string = date.strftime("%Y-%m-%d")
        room, time_slots, weekdays, dates = show_room(room.slug, date_string)

        # Check the length of returned lists
        number_of_timeslots = 36
        assert len(time_slots) == number_of_timeslots
        number_of_weekdays = 7
        assert len(weekdays) == number_of_weekdays

        # Check some sample values
        assert time_slots[0]["time"] == timezone.datetime(
            2024, 7, 22, 6, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
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

        assert dates["shown_date"] == timezone.make_naive(date).date()
        assert (
            dates["previous_week"]
            == timezone.make_naive(date - timedelta(days=7)).date()
        )
        assert (
            dates["next_week"] == timezone.make_naive(date + timedelta(days=7)).date()
        )

    def test_some_bookings_exist(self):
        room = RoomFactory()
        booking1 = BookingFactory(
            room=room,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 8, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 9, 0)),
            ),
        )
        booking2 = BookingFactory(
            room=room,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 18, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 22, 0)),
            ),
        )
        booking1.save()
        booking2.save()

        date = timezone.make_aware(timezone.datetime(2024, 6, 5))

        date_string = date.strftime("%Y-%m-%d")
        room, time_slots, weekdays, dates = show_room(room.slug, date_string)

        number_of_timeslots = 36
        assert len(time_slots) == number_of_timeslots
        number_of_weekdays = 7
        assert len(weekdays) == number_of_weekdays

        assert (
            time_slots[4]["booked"][2] is True
        )  # This should be True because we booked the slot from 8:00 to 9:00
        assert (
            time_slots[14]["booked"][2] is False
        )  # This should be False because we did not book the slot
        assert (
            time_slots[24]["booked"][2] is True
        )  # This should be True because we booked the slot from 18:00 to 22:00

    def test_without_date(self):
        date_string = None
        room = RoomFactory()
        room, time_slots, weekdays, dates = show_room(room.slug, date_string)
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
    ("persons_count", "start_datetime", "expected"),
    [
        ("2", None, ["Room1", "Room2"]),
        ("1", "2024-07-25T12:30", ["Room1", "Room2", "Small Room"]),
        ("3", None, ["Room2"]),
        (None, None, ["Room1", "Room2", "Small Room"]),
    ],
)
def test_filter_rooms(persons_count, start_datetime, expected):
    RoomFactory.create(name="Room1", max_persons=2)
    RoomFactory.create(name="Room2", max_persons=3)
    RoomFactory.create(name="Small Room", max_persons=1)

    rooms = filter_rooms(persons_count, start_datetime)
    assert {room.name for room in rooms} == set(expected)


class TestGetAccessCode(TestCase):
    """
    Given an organization, room and a timestamp,
    when I ask for an access code for that room,
    I get back the correct code.
    """

    def setUp(self):
        self.timestamp = timezone.make_aware(timezone.datetime(2024, 7, 23, 13, 30))
        self.access1 = AccessFactory()
        self.access2 = AccessFactory()
        self.room1 = RoomFactory(access=self.access1)
        self.room2 = RoomFactory(access=self.access2)
        self.organization1 = OrganizationFactory()
        self.organization2 = OrganizationFactory()
        self.access_code1 = AccessCodeFactory(
            access=self.access1, validity_start=self.timestamp, organization=None
        )
        self.access_code2 = AccessCodeFactory(
            access=self.access1,
            validity_start=self.timestamp + timedelta(days=7),
            organization=self.organization2,
        )
        self.access_code3 = AccessCodeFactory(
            access=self.access1,
            validity_start=self.timestamp + timedelta(days=14),
            organization=None,
        )

    def test_get_general_access_code(self):
        # gets as access_code1, as there is no access_key having a specific organization
        assert (
            get_access_code(
                room_slug=self.room1.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=1)),
            )
            == self.access_code1
        )

        # we should still get back access_code1,
        # because access_code2 is only for organization2
        assert (
            get_access_code(
                room_slug=self.room1.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=10)),
            )
            == self.access_code1
        )

        # we should get back access_code2,
        # because access_code2 is only for organization2
        assert (
            get_access_code(
                room_slug=self.room1.slug,
                organization_slug=self.organization2.slug,
                timestamp=(self.timestamp + timedelta(days=10)),
            )
            == self.access_code2
        )

        assert (
            get_access_code(
                room_slug=self.room2.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=1)),
            )
            is None
        )


class TestRoomPlanner(TestCase):
    def test_empty_planner_table(self):
        date = timezone.make_aware(timezone.datetime(2024, 7, 23))
        date_string = date.strftime("%Y-%m-%d")

        room1 = RoomFactory()
        room2 = RoomFactory()
        rooms, timeslots, dates = planner_table(date_string)

        number_of_timeslots = 48
        assert len(timeslots) == number_of_timeslots
        assert set(rooms) == {room1, room2}

        # Check some sample values
        assert (
            dates["previous_day"]
            == timezone.make_naive(date - timedelta(days=1)).date()
        )
        assert dates["next_day"] == timezone.make_naive(date + timedelta(days=1)).date()
        assert dates["shown_date"] == timezone.make_naive(date).date()
        assert timeslots[16]["time"] == timezone.datetime(
            2024, 7, 23, 8, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
        )
        assert timeslots[16]["booked"] == [
            False,
            False,
        ]

        # Check that every slot is False (not booked)
        for slot in timeslots:
            assert all(booked is False for booked in slot["booked"])

    def test_some_bookings_exist(self):
        room1 = RoomFactory()
        room2 = RoomFactory()
        booking1 = BookingFactory(
            room=room1,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 5, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 9, 0)),
            ),
        )
        booking2 = BookingFactory(
            room=room1,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 18, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 22, 0)),
            ),
        )
        booking3 = BookingFactory(
            room=room2,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 23, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 6, 22, 0)),
            ),
        )
        booking1.save()
        booking2.save()
        booking3.save()

        date = timezone.make_aware(timezone.datetime(2024, 6, 5))

        date_string = date.strftime("%Y-%m-%d")
        rooms, timeslots, dates = planner_table(date_string)

        number_of_timeslots = 48
        assert len(timeslots) == number_of_timeslots

        assert (
            timeslots[16]["booked"][0] is True
        )  # This should be True because we booked the slot from 8:00 to 9:00
        assert (
            timeslots[26]["booked"][0] is False
        )  # This should be False because we did not book the slot
        assert timeslots[36]["booked"][0] is True  # This should be False
        assert (
            timeslots[36]["booked"][1] is False
        )  # This should be True because we booked the slot from 18:00 to 22:00
