from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import RecurrenceRule
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.tests.factories import BookingMessageFactory
from roomsharing.bookings.tests.factories import RecurrenceRuleFactory


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


def test_recurrence_rule_get_absolute_url(recurrence_rule: RecurrenceRule):
    assert (
        recurrence_rule.get_absolute_url()
        == f"/bookings/recurrences/{recurrence_rule.uuid}/"
    )


@pytest.mark.django_db()
def test_human_readable_rule():
    # DAILY
    rrule1 = RecurrenceRuleFactory(rrule="FREQ=DAILY;INTERVAL=1;COUNT=5")
    assert rrule1.get_human_readable_rule() == "every day, ends after 5 times"

    rrule2 = RecurrenceRuleFactory(rrule="FREQ=DAILY;INTERVAL=3;UNTIL=20241204T000000")
    assert rrule2.get_human_readable_rule() == "every 3rd day, ends at the 12/04/2024"

    # WEEKLY
    rrule3 = RecurrenceRuleFactory(rrule="FREQ=WEEKLY;COUNT=3;BYDAY=MO,TU,FR")
    assert (
        rrule3.get_human_readable_rule()
        == "every week (only Mondays, Tuesdays, Fridays), ends after 3 times"
    )

    rrule4 = RecurrenceRuleFactory(
        rrule="FREQ=WEEKLY;INTERVAL=5;UNTIL=20241204T000000;BYDAY=MO,TU,WE,TH,FR,SA,SU"
    )
    assert (
        rrule4.get_human_readable_rule()
        == "every 5th week (on all days of the week), ends at the 12/04/2024"
    )

    # MONTHLY (by day)
    rrule5 = RecurrenceRuleFactory(rrule="FREQ=MONTHLY;COUNT=4;BYDAY=+1MO,+3TU,-1FR")
    assert (
        rrule5.get_human_readable_rule()
        == "every month at the 1. Monday, 3. Tuesday, last Friday, ends after 4 times"
    )

    rrule6 = RecurrenceRuleFactory(
        rrule="FREQ=MONTHLY;INTERVAL=2;UNTIL=20241204T000000;BYDAY=+4FR"
    )
    assert (
        rrule6.get_human_readable_rule()
        == "every 2nd month at the 4. Friday, ends at the 12/04/2024"
    )

    # MONTHLY (by date)
    rrule7 = RecurrenceRuleFactory(rrule="FREQ=MONTHLY;COUNT=4;BYMONTHDAY=1,4,31")
    assert (
        rrule7.get_human_readable_rule()
        == "every month (only at the 1., 4., 31. day), ends after 4 times"
    )

    rrule8 = RecurrenceRuleFactory(
        rrule="FREQ=MONTHLY;INTERVAL=1;UNTIL=20241204T000000;BYMONTHDAY=18"
    )
    assert (
        rrule8.get_human_readable_rule()
        == "every month (only at the 18. day), ends at the 12/04/2024"
    )


@pytest.mark.django_db()
def test_number_of_occurrences():
    rrule = RecurrenceRuleFactory(rrule="FREQ=DAILY;INTERVAL=1;COUNT=10")
    BookingFactory(recurrence_rule=rrule)
    BookingFactory(recurrence_rule=rrule)
    BookingFactory(recurrence_rule=rrule)
    assert rrule.number_of_occurrences() == 3  # noqa: PLR2004


@pytest.mark.django_db()
def test_get_first_booking():
    rrule = RecurrenceRuleFactory(rrule="FREQ=DAILY;INTERVAL=1;COUNT=10")
    start_date = timezone.now()
    b1 = BookingFactory(recurrence_rule=rrule, start_date=start_date.date())
    BookingFactory(recurrence_rule=rrule, start_date=start_date + timedelta(days=1))
    BookingFactory(recurrence_rule=rrule, start_date=start_date + timedelta(days=1))
    assert rrule.get_first_booking() == b1
