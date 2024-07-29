from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from roomsharing.bookings.models import BookingMessage
from roomsharing.bookings.services import InvalidBookingOperationError
from roomsharing.bookings.services import cancel_booking
from roomsharing.bookings.services import confirm_booking
from roomsharing.bookings.services import create_bookingmessage
from roomsharing.bookings.services import get_booking_activity_stream
from roomsharing.bookings.services import save_booking
from roomsharing.bookings.services import save_bookingmessage
from roomsharing.bookings.services import show_booking
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.tests.factories import BookingPermissionFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.rooms.tests.factories import AccessCodeFactory
from roomsharing.rooms.tests.factories import AccessFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.users.tests.factories import UserFactory
from roomsharing.utils.models import BookingStatus


class TestCancelBooking(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.booking = BookingFactory(organization=self.organization)

    def test_no_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.PENDING,
        )
        with pytest.raises(PermissionDenied):
            cancel_booking(self.user, self.booking.slug)

    def test_booking_not_cancelable(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus.CANCELLED
        self.booking.save()
        with pytest.raises(InvalidBookingOperationError):
            cancel_booking(self.user, self.booking.slug)

    def test_booking_cancelable(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus.CONFIRMED
        start = timezone.now() + timedelta(days=1)
        self.booking.timespan = (start, start + timedelta(hours=2))
        self.booking.save()
        cancel_booking(self.user, self.booking.slug)
        self.booking.refresh_from_db()

        assert self.booking.status == BookingStatus.CANCELLED


class TestBookingActivityStream(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.booking = BookingFactory(
            organization=self.organization, status=BookingStatus.PENDING
        )

    def test_activity_stream(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        start = timezone.now() + timedelta(days=1)
        self.booking.timespan = (start, start + timedelta(hours=2))
        self.booking.save()
        cancel_booking(self.user, self.booking.slug)

        bookingmessage = "Hello, but I still need a room"
        save_bookingmessage(self.booking, bookingmessage, self.user)
        self.booking.refresh_from_db()

        activity_stream = get_booking_activity_stream(self.booking)
        assert activity_stream[0]["type"] == "message"
        assert activity_stream[0]["text"] == bookingmessage
        assert activity_stream[0]["user"] == self.user

        assert activity_stream[1]["type"] == "status_change"
        assert activity_stream[1]["user"] == self.user
        status_text_mapping = dict(BookingStatus.choices)
        assert activity_stream[1]["old_status"] == [
            BookingStatus.PENDING,
            status_text_mapping[BookingStatus.PENDING],
        ]
        assert activity_stream[1]["new_status"] == [
            BookingStatus.CANCELLED,
            status_text_mapping[BookingStatus.CANCELLED],
        ]


class TestShowBooking(TestCase):
    def setUp(self):
        self.access = AccessFactory()
        self.room = RoomFactory(access=self.access)
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.start_datetime = timezone.now() + timedelta(days=10)
        self.booking = BookingFactory(
            organization=self.organization,
            status=BookingStatus.PENDING,
            room=self.room,
            timespan=(self.start_datetime, self.start_datetime + timedelta(hours=2)),
        )
        validity_start = self.start_datetime - timedelta(days=1)
        self.access_code = AccessCodeFactory(
            access=self.access,
            validity_start=validity_start,
            organization=self.organization,
        )

    def test_no_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.PENDING,
        )
        with pytest.raises(PermissionDenied):
            show_booking(self.user, self.booking.slug)

    def test_access_code_for_cancelled_booking(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus.CANCELLED
        booking, activity_stream, access_code = show_booking(
            self.user, self.booking.slug
        )
        assert access_code is None

    def test_access_code_for_pending_booking(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus.PENDING
        booking, activity_stream, access_code = show_booking(
            self.user, self.booking.slug
        )
        assert access_code is None

    def test_access_code_for_confirmed_booking(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        confirm_booking(self.user, self.booking.slug)
        booking, activity_stream, access_code = show_booking(
            self.user, self.booking.slug
        )
        assert access_code == self.access_code


class TestSaveBooking(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.room = RoomFactory()
        self.booking = BookingFactory(
            status=BookingStatus.PENDING, organization=self.organization
        )

    def test_save_booking_without_message(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus(BookingStatus.CONFIRMED)
        save_booking(self.user, self.booking, message=None)
        self.booking.refresh_from_db()

        assert self.booking.status == BookingStatus.CONFIRMED
        assert (
            BookingMessage.objects.filter(user=self.user, booking=self.booking).count()
            == 0
        )

    def test_save_booking_with_message(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        message = "I need a room!"
        self.booking.status = BookingStatus(BookingStatus.CONFIRMED)
        save_booking(self.user, self.booking, message)
        self.booking.refresh_from_db()

        assert self.booking.status == BookingStatus.CONFIRMED
        booking_message = BookingMessage.objects.filter(
            user=self.user, booking=self.booking
        ).first()
        assert booking_message.text == message
        assert booking_message.user == self.user

    def test_no_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.PENDING,
        )
        with pytest.raises(PermissionDenied):
            save_booking(self.user, self.booking, message=None)


class TestCreateBookingMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.room = RoomFactory()
        self.booking = BookingFactory(
            status=BookingStatus.PENDING, organization=self.organization
        )

    def test_create_bookingmessage_valid(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        form = Mock()
        form.is_valid.return_value = True
        text_message = "I need a room!"
        form.cleaned_data = {"text": text_message}
        create_bookingmessage(self.booking.slug, form, self.user)
        booking_message = BookingMessage.objects.filter(
            user=self.user, booking=self.booking
        ).first()

        assert booking_message.text == text_message
        assert booking_message.user == self.user

    def test_create_bookingmessage_invalid(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        form = Mock()  # Assuming form is a Django form
        form.is_valid.return_value = False
        with pytest.raises(InvalidBookingOperationError):
            create_bookingmessage(self.booking.slug, form, self.user)

    def test_no_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.PENDING,
        )
        form = Mock()  # Assuming form is a Django form
        form.is_valid.return_value = True
        with pytest.raises(PermissionDenied):
            create_bookingmessage(self.booking.slug, form, self.user)


class TestSaveBookingMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.booking = BookingFactory(
            status=BookingStatus.PENDING, organization=self.organization
        )

    def test_save_booking_message(self):
        message_text = "This is a new message!"
        booking_message_returned = save_bookingmessage(
            self.booking, message_text, self.user
        )

        assert booking_message_returned.text == message_text
        assert booking_message_returned.user == self.user
        assert booking_message_returned.booking == self.booking

        booking_message_in_db = BookingMessage.objects.filter(
            user=self.user, booking=self.booking
        ).first()

        assert booking_message_in_db.text == message_text
        assert booking_message_in_db.user == self.user
        assert booking_message_in_db.booking == self.booking


class TestGetBooking(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.booking = BookingFactory(
            status=BookingStatus.PENDING, organization=self.organization
        )
