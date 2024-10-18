from datetime import timedelta

import pytest
from django.utils import timezone

from roomsharing.bookings.forms import BookingForm
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.organizations.tests.factories import BookingPermissionFactory


@pytest.fixture()
def booking_db(room):
    start_datetime = timezone.now() + timedelta(days=1)
    end_datetime = start_datetime + timedelta(hours=1)
    return BookingFactory(room=room, timespan=(start_datetime, end_datetime), status=2)


@pytest.mark.django_db()
@pytest.mark.parametrize(
    (
        "startdate",
        "starttime",
        "endtime",
        "rrule_repetitions",
        "rrule_ends",
        "rrule_ends_count",
        "rrule_ends_enddate",
        "expected_errors",
    ),
    [
        (
            timezone.now().date() + timedelta(days=1),
            "11:00",
            "09:00",
            "NO_REPETITIONS",
            "NEVER",
            None,
            None,
            ["endtime", "starttime"],
        ),
        (
            timezone.now().date() - timedelta(days=1),
            "09:00",
            "11:00",
            "NO_REPETITIONS",
            "NEVER",
            None,
            None,
            ["startdate", "starttime"],
        ),
        (
            timezone.now().date(),
            "09:00",
            "11:00",
            "DAILY",
            "AFTER_TIMES",
            None,
            None,
            ["rrule_ends_count"],
        ),
        (
            timezone.now().date(),
            "09:00",
            "11:00",
            "DAILY",
            "AT_DATE",
            None,
            timezone.now().date() - timedelta(days=1),
            ["rrule_ends_enddate"],
        ),
        (
            timezone.now().date() + timedelta(days=731),
            "09:00",
            "11:00",
            "NO_REPETITIONS",
            "NEVER",
            None,
            None,
            ["startdate"],
        ),
    ],
)
def test_clean_method(  # noqa: PLR0913
    startdate,
    starttime,
    endtime,
    rrule_repetitions,
    rrule_ends,
    rrule_ends_count,
    rrule_ends_enddate,
    expected_errors,
    user,
    room,
    organization,
    booking_db,
    compensation,
):
    BookingPermissionFactory(organization=organization, user=user, status=2)
    form_data = {
        "startdate": startdate,
        "starttime": starttime,
        "endtime": endtime,
        "rrule_repetitions": rrule_repetitions,
        "rrule_ends": rrule_ends,
        "rrule_ends_count": rrule_ends_count,
        "rrule_ends_enddate": rrule_ends_enddate,
        "title": "Test title",
        "organization": organization.id,
        "room": room.id,
        "number_of_attendees": 20,
        "message": "Test message",
        "compensation": compensation.id,
    }
    form = BookingForm(user=user, data=form_data)

    assert not form.is_valid()
    for field in expected_errors:
        assert field in form.errors
