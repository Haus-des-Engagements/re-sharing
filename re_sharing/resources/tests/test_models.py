from datetime import timedelta

import pytest
from dateutil.parser import parse
from django.test import TestCase
from django.utils import timezone
from psycopg.types.range import Range

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.resources.models import Access
from re_sharing.resources.models import AccessCode
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import RoomFactory
from re_sharing.utils.models import BookingStatus


def test_resource_get_absolute_url(resource: Resource):
    assert resource.get_absolute_url() == f"/resources/{resource.slug}/"


class TestRoomIsBooked(TestCase):
    def setUp(self):
        self.resource = RoomFactory()
        self.now = timezone.now()

    def test_is_booked_when_resource_is_booked(self):
        BookingFactory(
            resource=self.resource,
            timespan=Range(
                self.now + timedelta(hours=1), self.now + timedelta(hours=2)
            ),
        )

        is_booked = self.resource.is_booked(
            Range(
                self.now + timedelta(hours=1, minutes=30), self.now + timedelta(hours=2)
            )
        )

        assert is_booked is True

    def test_is_booked_when_resource_is_not_booked(self):
        BookingFactory(
            resource=self.resource,
            timespan=Range(
                self.now + timedelta(hours=3), self.now + timedelta(hours=4)
            ),
        )

        is_booked = self.resource.is_booked(
            Range(self.now + timedelta(hours=1), self.now + timedelta(hours=2))
        )

        assert is_booked is False


def test_resource_str(resource: Resource):
    assert resource.__str__() == resource.name


def test_access_str(access: Access):
    assert access.__str__() == access.name


def test_access_code_str(access_code: AccessCode):
    assert (
        access_code.__str__()
        == access_code.access.name
        + " "
        + access_code.validity_start.strftime("%Y-%m-%d %H:%M")
    )


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("start_datetime", "booking_exists", "expected"),
    [
        (
            "2024-07-25T12:00",
            False,
            True,
        ),  # Resource is not yet booked, so it should be bookable
        (
            "2024-07-25T12:00",
            True,
            False,
        ),  # Resource is already booked, so it should not be bookable
        (
            "2024-07-25T12:20",
            True,
            False,
        ),  # Resource is booked and new booking overlaps, so it should not be bookable
    ],
)
def test_resource_is_bookable(start_datetime, booking_exists, expected):
    # Create a resource instance
    resource = RoomFactory(name="TestRoom")

    # Create a confirmed booking if booking_exists parameter is True
    if booking_exists:
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(parse("2024-07-25T12:00")),
                timezone.make_aware(parse("2024-07-25T12:30")),
            ),
        )

    # Call the is_bookable method on the resource instance
    result = resource.is_bookable(timezone.make_aware(parse(start_datetime)))

    # Assert the result is as expected
    assert result == expected
