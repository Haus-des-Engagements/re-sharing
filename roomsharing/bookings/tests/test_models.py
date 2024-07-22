from django.test import TestCase

from roomsharing.bookings.models import Booking
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.tests.factories import BookingMessageFactory


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
