from datetime import datetime
from datetime import timedelta
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingMessage
from roomsharing.bookings.services import InvalidBookingOperationError
from roomsharing.bookings.services import cancel_booking
from roomsharing.bookings.services import cancel_rrule_bookings
from roomsharing.bookings.services import confirm_booking
from roomsharing.bookings.services import create_booking
from roomsharing.bookings.services import create_bookingmessage
from roomsharing.bookings.services import create_rrule_string
from roomsharing.bookings.services import filter_bookings_list
from roomsharing.bookings.services import get_booking_activity_stream
from roomsharing.bookings.services import manager_cancel_booking
from roomsharing.bookings.services import manager_confirm_booking
from roomsharing.bookings.services import manager_filter_bookings_list
from roomsharing.bookings.services import save_booking
from roomsharing.bookings.services import save_bookingmessage
from roomsharing.bookings.services import show_booking
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.tests.factories import RecurrenceRuleFactory
from roomsharing.bookings.tests.factories import create_timespan
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


@pytest.mark.django_db()
def test_cancel_recurring_bookings():
    user = UserFactory()
    organization = OrganizationFactory()
    BookingPermissionFactory(
        user=user, organization=organization, status=BookingPermission.Status.CONFIRMED
    )

    rrule = RecurrenceRuleFactory()
    booking1 = BookingFactory(
        user=user,
        organization=organization,
        recurrence_rule=rrule,
        start_date=timezone.now().date() - timedelta(days=5),
        status=BookingStatus.PENDING,
    )
    booking2 = BookingFactory(
        user=user,
        organization=organization,
        recurrence_rule=rrule,
        start_date=timezone.now().date() + timedelta(days=10),
        status=BookingStatus.PENDING,
    )
    booking3 = BookingFactory(
        user=user,
        organization=organization,
        recurrence_rule=rrule,
        start_date=timezone.now().date() + timedelta(days=5),
        status=BookingStatus.PENDING,
    )

    cancel_rrule_bookings(user, rrule.uuid)

    booking1.refresh_from_db()
    booking2.refresh_from_db()
    booking3.refresh_from_db()

    assert booking1.status == BookingStatus.PENDING
    assert booking2.status == BookingStatus.CANCELLED
    assert booking3.status == BookingStatus.CANCELLED


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
        assert access_code == "only shown when confirmed"

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
        assert access_code == "only shown when confirmed"

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
        assert str(access_code) == str(self.access_code.code)


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


@pytest.mark.django_db()
@pytest.mark.parametrize(
    (
        "show_past_bookings",
        "organization",
        "status",
        "hide_recurring_bookings",
        "expected",
    ),
    [
        (True, "all", "all", True, 2),
        (True, "all", [1], True, 1),
        (False, "all", "all", True, 1),
        (True, "org1", "all", True, 0),
    ],
)
def test_filter_bookings_list(
    show_past_bookings, organization, status, hide_recurring_bookings, expected
):
    """
    Test the 'filter_bookings_list' function
    """
    # Arrange
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationFactory(name="org1")
    BookingPermissionFactory(
        organization=org, user=user, status=BookingPermission.Status.CONFIRMED
    )
    BookingFactory(
        user=user,
        organization=org,
        status=BookingStatus.PENDING,
        timespan=(
            timezone.now() + timezone.timedelta(days=1),
            timezone.now() + timezone.timedelta(days=1, hours=1),
        ),
    )
    BookingFactory(
        user=user,
        organization=org,
        timespan=(
            timezone.now() - timezone.timedelta(days=1, hours=2),
            timezone.now() - timezone.timedelta(days=1),
        ),
    )
    # Act
    bookings, organizations = filter_bookings_list(
        organization, show_past_bookings, status, user, hide_recurring_bookings
    )
    # Assert
    assert len(bookings) == expected


@pytest.mark.django_db()
def test_create_booking():
    """Test the create_booking function."""

    # Arrange
    user = UserFactory()
    organization = OrganizationFactory()
    room = RoomFactory()
    timespan = create_timespan(None, None)

    booking_details = {
        "user": user,
        "title": "Test Booking",
        "room": room,
        "timespan": timespan,
        "organization": organization,
        "status": BookingStatus.PENDING,
        "start_date": timespan.lower.date(),
        "start_time": timespan.lower.time(),
        "end_time": timespan.upper.time(),
        "compensation": None,
        "total_amount": None,
    }
    kwargs = {"room_booked": True, "rrule": "FREQ=DAILY"}

    # Act
    booking = create_booking(booking_details, **kwargs)

    # Assert
    assert isinstance(booking, Booking)
    assert booking.user == booking_details["user"]
    assert booking.title == booking_details["title"]
    assert booking.room == booking_details["room"]
    assert booking.timespan == booking_details["timespan"]
    assert booking.organization == booking_details["organization"]
    assert booking.status == booking_details["status"]
    assert booking.start_date == booking_details["start_date"]
    assert booking.start_time == booking_details["start_time"]
    assert booking.end_time == booking_details["end_time"]
    assert booking.room_booked == kwargs["room_booked"]
    assert booking.rrule == kwargs["rrule"]
    assert booking.compensation is None
    assert booking.total_amount is None
    assert not booking.pk  # Not saved in the database


@pytest.mark.django_db()
@pytest.mark.parametrize(
    (
        "show_past_bookings",
        "organization",
        "status",
        "hide_recurring_bookings",
        "expected",
    ),
    [
        (True, "all", "all", True, 2),
        (True, "all", [1], True, 1),
        (False, "all", "all", True, 1),
        (True, "org1", "all", True, 0),
    ],
)
def test_manger_filter_bookings_list(
    show_past_bookings, organization, status, hide_recurring_bookings, expected
):
    """
    Test the 'filter_bookings_list' function
    """
    # Arrange
    user = UserFactory()
    org = OrganizationFactory()
    OrganizationFactory(name="org1")
    BookingFactory(
        user=user,
        organization=org,
        status=BookingStatus.PENDING,
        timespan=(
            timezone.now() + timezone.timedelta(days=1),
            timezone.now() + timezone.timedelta(days=1, hours=1),
        ),
    )
    BookingFactory(
        user=user,
        organization=org,
        timespan=(
            timezone.now() - timezone.timedelta(days=1, hours=2),
            timezone.now() - timezone.timedelta(days=1),
        ),
    )
    # Act
    bookings, organizations = manager_filter_bookings_list(
        organization, show_past_bookings, status, hide_recurring_bookings
    )
    # Assert
    assert len(bookings) == expected


@pytest.mark.parametrize(
    ("rrule_data", "expected"),
    [
        (
            {
                "rrule_repetitions": "DAILY",
                "rrule_ends": "AFTER_TIMES",
                "rrule_ends_count": 5,
                "rrule_ends_enddate": None,
                "rrule_daily_interval": 1,
                "rrule_weekly_interval": None,
                "rrule_weekly_byday": None,
                "rrule_monthly_interval": None,
                "rrule_monthly_bydate": None,
                "rrule_monthly_byday": None,
                "startdate": datetime.date(2023, 10, 1),
            },
            "DTSTART:20231001T000000\nRRULE:FREQ=DAILY;COUNT=5",
        ),
        (
            {
                "rrule_repetitions": "WEEKLY",
                "rrule_ends": "UNTIL_DATE",
                "rrule_ends_count": None,
                "rrule_ends_enddate": datetime.date(2023, 12, 31),
                "rrule_daily_interval": None,
                "rrule_weekly_interval": 1,
                "rrule_weekly_byday": ["MO", "WE", "FR"],
                "rrule_monthly_interval": None,
                "rrule_monthly_bydate": None,
                "rrule_monthly_byday": None,
                "startdate": datetime.date(2023, 10, 1),
            },
            "DTSTART:20231001T000000\nRRULE:FREQ=WEEKLY;UNTIL=20231231T000000;BYDAY=MO,WE,FR",
        ),
        (
            {
                "rrule_repetitions": "MONTHLY_BY_DAY",
                "rrule_ends": "UNTIL_DATE",
                "rrule_ends_count": None,
                "rrule_ends_enddate": datetime.date(2023, 12, 31),
                "rrule_daily_interval": None,
                "rrule_weekly_interval": 1,
                "rrule_weekly_byday": None,
                "rrule_monthly_interval": 2,
                "rrule_monthly_bydate": None,
                "rrule_monthly_byday": ["MO(1)", "WE(3)", "SU(-1)"],
                "startdate": datetime.date(2023, 10, 1),
            },
            "DTSTART:20231001T000000\nRRULE:FREQ=MONTHLY;INTERVAL=2;UNTIL=20231231T000000;BYDAY=+1MO,+3WE,-1SU",
        ),
        (
            {
                "rrule_repetitions": "MONTHLY_BY_DATE",
                "rrule_ends": "UNTIL_DATE",
                "rrule_ends_count": None,
                "rrule_ends_enddate": datetime.date(2023, 12, 31),
                "rrule_daily_interval": None,
                "rrule_weekly_interval": None,
                "rrule_weekly_byday": None,
                "rrule_monthly_interval": 3,
                "rrule_monthly_bydate": [1, 12, 30],
                "rrule_monthly_byday": None,
                "startdate": datetime.date(2023, 10, 1),
            },
            "DTSTART:20231001T000000\nRRULE:FREQ=MONTHLY;INTERVAL=3;UNTIL=20231231T000000;BYMONTHDAY=1,12,30",
        ),
    ],
)
def test_create_rrule_string(rrule_data, expected):
    result = create_rrule_string(rrule_data)
    assert result == expected


@pytest.mark.django_db()
@patch.object(Booking, "is_confirmable", return_value=True)
def test_manager_confirm_booking(mock_is_confirmable):
    user = UserFactory()
    booking = BookingFactory()

    booking = manager_confirm_booking(user, booking.slug)

    # Assertions
    assert booking.status == BookingStatus.CONFIRMED


@pytest.mark.django_db()
@patch.object(Booking, "is_confirmable", return_value=False)
def test_manager_confirm_booking_not_confirmable(mock_is_confirmable):
    user = UserFactory()
    booking = BookingFactory(status=BookingStatus.PENDING)
    with pytest.raises(InvalidBookingOperationError):
        manager_confirm_booking(user, booking.slug)


@pytest.mark.django_db()
@patch.object(Booking, "is_cancelable", return_value=True)
def test_manager_cancel_booking(mock_is_cancelable):
    user = UserFactory()
    booking = BookingFactory()
    booking = manager_cancel_booking(user, booking.slug)

    # Assertions
    assert booking.status == BookingStatus.CANCELLED


@pytest.mark.django_db()
@patch.object(Booking, "is_cancelable", return_value=False)
def test_manager_cancel_booking_not_cancelable(mock_is_cancelable):
    user = UserFactory()
    booking = BookingFactory()
    with pytest.raises(InvalidBookingOperationError):
        manager_confirm_booking(user, booking.slug)
