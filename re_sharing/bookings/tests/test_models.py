from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingMessageFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.utils.models import BookingStatus


def test_booking_get_absolute_url(booking: Booking):
    assert booking.get_absolute_url() == f"/bookings/{booking.slug}/"


class BookingMessageTestCase(TestCase):
    def setUp(self):
        self.booking = BookingFactory()
        self.bookingmessage = BookingMessageFactory(booking=self.booking)

    def test_booking_get_absolute_url(self):
        assert (
            self.bookingmessage.get_absolute_url() == f"/bookings/{self.booking.slug}/"
        )


def test_booking_series_get_absolute_url(booking_series: BookingSeries):
    assert (
        booking_series.get_absolute_url()
        == f"/bookings/recurrences/{booking_series.slug}/"
    )


@pytest.mark.django_db()
def test_human_readable_rule():
    one_year_from_now = timezone.now() + timedelta(days=365)
    until_date_str = one_year_from_now.strftime("%Y%m%dT000000")
    expected_end_date_str = one_year_from_now.strftime("%m/%d/%Y")

    # DAILY
    rrule1 = BookingSeriesFactory(rrule="FREQ=DAILY;INTERVAL=1;COUNT=5")
    assert rrule1.get_human_readable_rule() == "every day, ends after 5 times"

    rrule2 = BookingSeriesFactory(rrule=f"FREQ=DAILY;INTERVAL=3;UNTIL={until_date_str}")
    assert (
        rrule2.get_human_readable_rule()
        == f"every 3rd day, ends at the {expected_end_date_str}"
    )

    # WEEKLY
    rrule3 = BookingSeriesFactory(rrule="FREQ=WEEKLY;COUNT=3;BYDAY=MO,TU,FR")
    assert (
        rrule3.get_human_readable_rule()
        == "every week (only Mondays, Tuesdays, Fridays), ends after 3 times"
    )

    rrule4 = BookingSeriesFactory(
        rrule=f"FREQ=WEEKLY;INTERVAL=5;UNTIL={until_date_str};BYDAY=MO,TU,WE,TH,FR,SA,SU"
    )
    assert (
        rrule4.get_human_readable_rule()
        == f"every 5th week (on all days of the week), "
        f"ends at the {expected_end_date_str}"
    )

    # MONTHLY (by day)
    rrule5 = BookingSeriesFactory(rrule="FREQ=MONTHLY;COUNT=4;BYDAY=+1MO,+3TU,-1FR")
    assert (
        rrule5.get_human_readable_rule()
        == "every month at the 1. Monday, 3. Tuesday, last Friday, ends after 4 times"
    )

    rrule6 = BookingSeriesFactory(
        rrule=f"FREQ=MONTHLY;INTERVAL=2;UNTIL={until_date_str};BYDAY=+4FR"
    )
    assert (
        rrule6.get_human_readable_rule()
        == f"every 2nd month at the 4. Friday, ends at the {expected_end_date_str}"
    )

    # MONTHLY (by date)
    rrule7 = BookingSeriesFactory(rrule="FREQ=MONTHLY;COUNT=4;BYMONTHDAY=1,4,31")
    assert (
        rrule7.get_human_readable_rule()
        == "every month (only at the 1., 4., 31. day), ends after 4 times"
    )

    rrule8 = BookingSeriesFactory(
        rrule=f"FREQ=MONTHLY;INTERVAL=1;UNTIL={until_date_str};BYMONTHDAY=18"
    )
    assert (
        rrule8.get_human_readable_rule()
        == f"every month (only at the 18. day), ends at the {expected_end_date_str}"
    )


@pytest.mark.django_db()
def test_number_of_occurrences():
    rrule = BookingSeriesFactory(rrule="FREQ=DAILY;INTERVAL=1;COUNT=10")
    BookingFactory(booking_series=rrule)
    BookingFactory(booking_series=rrule)
    BookingFactory(booking_series=rrule)
    assert rrule.number_of_occurrences() == 3  # noqa: PLR2004


@pytest.mark.django_db()
def test_get_first_booking():
    rrule = BookingSeriesFactory(rrule="FREQ=DAILY;INTERVAL=1;COUNT=10")
    start_date = timezone.now()
    b1 = BookingFactory(booking_series=rrule, start_date=start_date.date())
    BookingFactory(booking_series=rrule, start_date=start_date + timedelta(days=1))
    BookingFactory(booking_series=rrule, start_date=start_date + timedelta(days=1))
    assert rrule.get_first_booking() == b1


@pytest.mark.django_db()
@pytest.mark.parametrize(
    (
        "booking1_start",
        "booking1_status",
        "booking2_start",
        "booking2_status",
        "expected",
    ),
    [
        # Test case 1: one booking in the past, one in the future --> True
        (
            timezone.now().date() - timedelta(days=5),
            BookingStatus.PENDING,
            timezone.now().date() + timedelta(days=10),
            BookingStatus.PENDING,
            True,
        ),
        # Test case 2: 2 bookings in the past --> False
        (
            timezone.now().date() - timedelta(days=5),
            BookingStatus.PENDING,
            timezone.now().date() - timedelta(days=3),
            BookingStatus.PENDING,
            False,
        ),
        # Test case 3: 2 bookings in the future, but 1 canceled --> True
        (
            timezone.now().date() + timedelta(days=5),
            BookingStatus.CANCELLED,
            timezone.now().date() + timedelta(days=10),
            BookingStatus.PENDING,
            True,
        ),
        # Test case 4: 2 Bookings in the future, but 2 canceled --> False
        (
            timezone.now().date() + timedelta(days=5),
            BookingStatus.CANCELLED,
            timezone.now().date() + timedelta(days=10),
            BookingStatus.CANCELLED,
            False,
        ),
    ],
)
def test_is_cancelable(
    booking1_start, booking1_status, booking2_start, booking2_status, expected
):
    rrule = BookingSeriesFactory()

    BookingFactory(
        booking_series=rrule,
        start_date=booking1_start,
        status=booking1_status,
    )
    BookingFactory(
        booking_series=rrule,
        start_date=booking2_start,
        status=booking2_status,
    )

    assert rrule.is_cancelable() is expected
