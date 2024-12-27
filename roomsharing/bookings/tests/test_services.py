import datetime
import zoneinfo
from datetime import timedelta
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from dateutil.rrule import rrulestr
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingMessage
from roomsharing.bookings.models import RecurrenceRule
from roomsharing.bookings.services import InvalidBookingOperationError
from roomsharing.bookings.services import cancel_booking
from roomsharing.bookings.services import collect_booking_reminder_mails
from roomsharing.bookings.services import confirm_booking
from roomsharing.bookings.services import create_booking
from roomsharing.bookings.services import create_bookingmessage
from roomsharing.bookings.services import filter_bookings_list
from roomsharing.bookings.services import generate_single_booking
from roomsharing.bookings.services import get_booking_activity_stream
from roomsharing.bookings.services import manager_cancel_booking
from roomsharing.bookings.services import manager_confirm_booking
from roomsharing.bookings.services import manager_confirm_rrule
from roomsharing.bookings.services import manager_filter_bookings_list
from roomsharing.bookings.services import save_booking
from roomsharing.bookings.services import save_bookingmessage
from roomsharing.bookings.services import set_initial_booking_data
from roomsharing.bookings.services import show_booking
from roomsharing.bookings.services_recurrences import cancel_rrule_bookings
from roomsharing.bookings.services_recurrences import create_rrule_and_occurrences
from roomsharing.bookings.services_recurrences import create_rrule_string
from roomsharing.bookings.services_recurrences import manager_cancel_rrule
from roomsharing.bookings.services_recurrences import save_rrule
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.tests.factories import RecurrenceRuleFactory
from roomsharing.bookings.tests.factories import create_timespan
from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.tests.factories import BookingPermissionFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.organizations.tests.factories import OrganizationGroupFactory
from roomsharing.rooms.tests.factories import AccessCodeFactory
from roomsharing.rooms.tests.factories import AccessFactory
from roomsharing.rooms.tests.factories import CompensationFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.users.tests.factories import UserFactory
from roomsharing.users.tests.factories import UserGroupFactory
from roomsharing.utils.models import BookingStatus
from roomsharing.utils.models import get_booking_status


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

    def test_save_booking(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus(BookingStatus.CONFIRMED)
        save_booking(self.user, self.booking)
        self.booking.refresh_from_db()

        assert self.booking.status == BookingStatus.CONFIRMED
        assert (
            BookingMessage.objects.filter(user=self.user, booking=self.booking).count()
            == 0
        )

    def test_no_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.PENDING,
        )
        with pytest.raises(PermissionDenied):
            save_booking(self.user, self.booking)


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
    show_past_bookings,
    organization,
    status,
    hide_recurring_bookings,
    expected,
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
        organization,
        show_past_bookings,
        status,
        user,
        hide_recurring_bookings,
        page_number=1,
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
        "end_date": timespan.lower.date(),
        "start_time": timespan.lower.time(),
        "end_time": timespan.upper.time(),
        "compensation": None,
        "total_amount": None,
        "differing_billing_address": None,
        "activity_description": "Just a meeting",
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
    assert booking.end_date == booking_details["end_date"]
    assert booking.start_time == booking_details["start_time"]
    assert booking.end_time == booking_details["end_time"]
    assert booking.room_booked == kwargs["room_booked"]
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
        "room",
        "date_string",
        "expected",
    ),
    [
        (True, "all", "all", True, "all", None, 2),
        (True, "all", [1], True, "all", None, 1),
        (False, "all", "all", True, "all", None, 1),
        (True, "org1", "all", True, "all", None, 0),
    ],
)
def test_manger_filter_bookings_list(  # noqa: PLR0913
    show_past_bookings,
    organization,
    status,
    hide_recurring_bookings,
    room,
    date_string,
    expected,
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
    bookings, organizations, rooms = manager_filter_bookings_list(
        organization,
        show_past_bookings,
        status,
        hide_recurring_bookings,
        room,
        date_string,
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
                "start": datetime.datetime(
                    2023, 10, 1, 20, 00, 00, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
                ),
            },
            "DTSTART:20231001T180000Z\nRRULE:FREQ=DAILY;COUNT=5",
        ),
        (
            {
                "rrule_repetitions": "WEEKLY",
                "rrule_ends": "AT_DATE",
                "rrule_ends_count": None,
                "rrule_ends_enddate": datetime.datetime(
                    2023, 12, 31, 20, 30, 00, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
                ),
                "rrule_daily_interval": None,
                "rrule_weekly_interval": 1,
                "rrule_weekly_byday": ["MO", "WE", "FR"],
                "rrule_monthly_interval": None,
                "rrule_monthly_bydate": None,
                "rrule_monthly_byday": None,
                "start": datetime.datetime(
                    2023, 10, 1, 10, 30, 00, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
                ),
            },
            "DTSTART:20231001T083000Z\nRRULE:FREQ=WEEKLY;UNTIL=20231231T193000Z;BYDAY=MO,WE,FR",
        ),
        (
            {
                "rrule_repetitions": "MONTHLY_BY_DAY",
                "rrule_ends": "AT_DATE",
                "rrule_ends_count": None,
                "rrule_ends_enddate": datetime.datetime(
                    2023, 12, 31, 20, 30, 00, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
                ),
                "rrule_daily_interval": None,
                "rrule_weekly_interval": 1,
                "rrule_weekly_byday": None,
                "rrule_monthly_interval": 2,
                "rrule_monthly_bydate": None,
                "rrule_monthly_byday": ["MO(1)", "WE(3)", "SU(-1)"],
                "start": datetime.datetime(
                    2023, 10, 1, 6, 00, 00, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
                ),
            },
            "DTSTART:20231001T040000Z\nRRULE:FREQ=MONTHLY;INTERVAL=2;UNTIL=20231231T193000Z;BYDAY=+1MO,+3WE,-1SU",
        ),
        (
            {
                "rrule_repetitions": "MONTHLY_BY_DATE",
                "rrule_ends": "NEVER",
                "rrule_ends_count": None,
                "rrule_ends_enddate": None,
                "rrule_daily_interval": None,
                "rrule_weekly_interval": None,
                "rrule_weekly_byday": None,
                "rrule_monthly_interval": 3,
                "rrule_monthly_bydate": [1, 12, 30],
                "rrule_monthly_byday": None,
                "start": datetime.datetime(
                    2023, 10, 1, 9, 30, tzinfo=zoneinfo.ZoneInfo("Europe/Berlin")
                ),
            },
            "DTSTART:20231001T073000Z\nRRULE:FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=1,12,30",
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


class TestGenerateSingleBooking(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.room = RoomFactory()
        self.compensation = CompensationFactory(hourly_rate=50, room=[self.room])
        self.start_datetime = timezone.now() + timedelta(days=1)
        self.duration = 2
        self.differing_billing_address = "Fast lane 2, 929 Free-City"
        self.end_datetime = self.start_datetime + timedelta(hours=self.duration)
        self.booking_data = {
            "user": self.user.slug,
            "title": "Meeting",
            "room": self.room.slug,
            "organization": self.organization.slug,
            "timespan": [
                self.start_datetime.isoformat(),
                self.end_datetime.isoformat(),
            ],
            "start_date": self.start_datetime.date(),
            "end_date": self.start_datetime.date(),
            "start_time": self.start_datetime.time(),
            "end_time": self.end_datetime.time(),
            "message": "Please confirm my booking",
            "compensation": self.compensation.id,
            "differing_billing_address": self.differing_billing_address,
            "activity_description": "Simple Meeting",
        }

    def test_generate_single_booking_valid_data(self):
        booking = generate_single_booking(self.booking_data)

        assert isinstance(booking, Booking)
        assert booking.user == self.user
        assert booking.title == "Meeting"
        assert booking.room == self.room
        assert booking.organization == self.organization
        assert booking.timespan == (self.start_datetime, self.end_datetime)
        assert booking.compensation == self.compensation
        assert booking.total_amount == self.compensation.hourly_rate * self.duration
        assert booking.activity_description == "Simple Meeting"
        assert booking.differing_billing_address == self.differing_billing_address

    def test_generate_single_booking_no_compensation(self):
        self.booking_data["compensation"] = ""
        self.booking_data["different_billing_address"] = ""
        booking = generate_single_booking(self.booking_data)

        assert isinstance(booking, Booking)
        assert booking.user == self.user
        assert booking.title == "Meeting"
        assert booking.room == self.room
        assert booking.organization == self.organization
        assert booking.timespan == (self.start_datetime, self.end_datetime)
        assert booking.compensation is None
        assert booking.total_amount is None

    def test_generate_single_booking_invalid_organization(self):
        self.booking_data["organization"] = "invalid-slug"

        with pytest.raises(Http404):
            generate_single_booking(self.booking_data)

    def test_generate_single_booking_invalid_room(self):
        self.booking_data["room"] = "invalid-slug"

        with pytest.raises(Http404):
            generate_single_booking(self.booking_data)

    def test_generate_single_booking_invalid_user(self):
        self.booking_data["user"] = "invalid-slug"

        with pytest.raises(Http404):
            generate_single_booking(self.booking_data)


class TestGenerateRecurrence(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.room = RoomFactory()
        self.compensation = CompensationFactory(hourly_rate=50)
        self.duration = 2
        self.start = (timezone.now() + timedelta(days=1)).replace(microsecond=0)
        self.dt_start = "DTSTART:" + self.start.strftime("%Y%m%dT%H%M%S") + "Z"
        self.end_datetime = (self.start + timedelta(hours=self.duration)).replace(
            microsecond=0
        )
        self.count = 5
        self.differing_billing_address = "Fast lane 2, 929 Free-City"
        self.rrule_string = self.dt_start + "\nFREQ=DAILY;COUNT=" + str(self.count)
        self.booking_data = {
            "user": self.user.slug,
            "title": "Recurring Meeting",
            "room": self.room.slug,
            "organization": self.organization.slug,
            "timespan": [
                self.start.isoformat(),
                self.end_datetime.isoformat(),
            ],
            "start_date": self.start.date(),
            "end_date": self.start.date(),
            "start_time": self.start.time().strftime("%H:%M:%S"),
            "end_time": self.end_datetime.time().strftime("%H:%M:%S"),
            "message": "Please confirm my recurring bookings",
            "compensation": self.compensation.id,
            "rrule_string": self.rrule_string,
            "start": self.start,
            "differing_billing_address": self.differing_billing_address,
            "activity_description": "Simple Meeting",
        }

    def test_generate_recurrence_valid_data(self):
        bookings, rrule, bookable = create_rrule_and_occurrences(self.booking_data)

        assert len(bookings) == self.count
        for booking in bookings:
            assert isinstance(booking, Booking)
            assert booking.user == self.user
            assert booking.title == "Recurring Meeting"
            assert booking.room == self.room
            assert booking.organization == self.organization
            assert booking.compensation == self.compensation
            assert booking.total_amount == self.compensation.hourly_rate * self.duration
            assert booking.differing_billing_address == self.differing_billing_address
            assert booking.activity_description == "Simple Meeting"

        assert isinstance(rrule, RecurrenceRule)
        rrule_occurrences = list(rrulestr(self.rrule_string))
        assert rrule.rrule == self.rrule_string
        assert rrule.first_occurrence_date == rrule_occurrences[0]
        assert rrule.last_occurrence_date == rrule_occurrences[-1]
        assert bookable is True

    def test_generate_recurrence_no_compensation(self):
        self.booking_data["compensation"] = ""
        self.booking_data["differing_billing_address"] = ""

        bookings, rrule, bookable = create_rrule_and_occurrences(self.booking_data)

        assert len(bookings) == self.count
        for booking in bookings:
            assert isinstance(booking, Booking)
            assert booking.user == self.user
            assert booking.title == "Recurring Meeting"
            assert booking.room == self.room
            assert booking.organization == self.organization
            assert booking.compensation is None
            assert booking.total_amount is None
            assert booking.differing_billing_address == ""

        assert isinstance(rrule, RecurrenceRule)
        rrule_occurrences = list(rrulestr(self.rrule_string))
        assert rrule.rrule == self.rrule_string
        assert rrule.start_time == self.start.time()
        assert rrule.end_time == self.end_datetime.time()
        assert rrule.first_occurrence_date == rrule_occurrences[0]
        assert rrule.last_occurrence_date == rrule_occurrences[-1]
        assert bookable is True

    def test_generate_recurrence_invalid_organization(self):
        self.booking_data["organization"] = "invalid-slug"

        with pytest.raises(Http404):
            create_rrule_and_occurrences(self.booking_data)

    def test_generate_recurrence_invalid_room(self):
        self.booking_data["room"] = "invalid-slug"

        with pytest.raises(Http404):
            create_rrule_and_occurrences(self.booking_data)

    def test_generate_recurrence_invalid_user(self):
        self.booking_data["user"] = "invalid-slug"

        with pytest.raises(Http404):
            create_rrule_and_occurrences(self.booking_data)


class TestSaveRecurrence(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.room = RoomFactory()
        self.compensation = CompensationFactory(hourly_rate=50)
        self.start = timezone.now() + timedelta(days=1)
        self.end = self.start + timedelta(hours=2)
        dtstart_string = self.start.strftime("%Y%m%dT%H%M00Z")
        self.rrule_string = f"DTSTART:{dtstart_string}\nFREQ=DAILY;COUNT=5"
        self.booking_data = {
            "user": self.user.slug,
            "title": "Recurring Meeting",
            "room": self.room.slug,
            "organization": self.organization.slug,
            "timespan": [
                self.start.isoformat(),
                self.end.isoformat(),
            ],
            "start_time": self.start.time().strftime("%H:%M:%S"),
            "end_time": self.end.time().strftime("%H:%M:%S"),
            "message": "Please confirm my recurring bookings",
            "compensation": self.compensation.id,
            "rrule_string": self.rrule_string,
            "start": self.start,
            "differing_billing_address": "",
            "activity_description": "Meeting with team members",
        }

        (
            self.bookings,
            self.rrule,
            self.bookable,
        ) = create_rrule_and_occurrences(self.booking_data)

    def test_save_recurrence_valid(self):
        # Add the booking permission for the user
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        bookings, rrule = save_rrule(self.user, self.bookings, self.rrule)

        for booking in bookings:
            assert booking.recurrence_rule == rrule

    def test_save_recurrence_permission_denied(self):
        # Do not add the booking permission for the user
        another_user = UserFactory()

        with pytest.raises(PermissionDenied):
            save_rrule(another_user, self.bookings, self.rrule)


@pytest.mark.django_db()
@patch.object(Booking, "is_cancelable", return_value=True)
def test_manager_cancel_rrule(mock_is_cancelable):
    user = UserFactory(is_staff=True)
    rrule = RecurrenceRuleFactory()
    booking1 = BookingFactory(recurrence_rule=rrule, status=BookingStatus.PENDING)
    booking2 = BookingFactory(recurrence_rule=rrule, status=BookingStatus.PENDING)

    manager_cancel_rrule(user, rrule.uuid)

    booking1.refresh_from_db()
    assert booking1.status == BookingStatus.CANCELLED
    booking2.refresh_from_db()
    assert booking2.status == BookingStatus.CANCELLED


@pytest.mark.django_db()
@patch.object(Booking, "is_confirmable", return_value=True)
def test_manager_confirm_rrule(mock_is_confirmable):
    user = UserFactory(is_staff=True)
    rrule = RecurrenceRuleFactory()
    booking1 = BookingFactory(recurrence_rule=rrule, status=BookingStatus.PENDING)
    booking2 = BookingFactory(recurrence_rule=rrule, status=BookingStatus.PENDING)

    manager_confirm_rrule(user, rrule.uuid)

    booking1.refresh_from_db()
    assert booking1.status == BookingStatus.CONFIRMED
    booking2.refresh_from_db()
    assert booking2.status == BookingStatus.CONFIRMED


class CollectBookingReminderMailsTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.in_5_days = self.now + timedelta(days=5)
        self.in_5_days = self.in_5_days.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.in_6_days = self.in_5_days + timedelta(days=1)

        # Creating a booking within the 5-6 days timespan
        self.booking = BookingFactory(
            slug="test-booking",
            status=BookingStatus.CONFIRMED,
            timespan=[self.in_5_days, self.in_6_days - timedelta(seconds=1)],
        )
        self.booking2 = BookingFactory(
            slug="test-booking_2",
            status=BookingStatus.CONFIRMED,
            timespan=[self.now, self.now + timedelta(hours=1)],
        )

    @patch("roomsharing.bookings.services.async_task")
    def test_collect_booking_reminder_mails(self, mock_async_task):
        collect_booking_reminder_mails()

        # Ensure the async_task was called exactly once
        assert mock_async_task.call_count == 1

        # Verify async_task was called with the correct arguments
        mock_async_task.assert_called_with(
            "roomsharing.organizations.mails.booking_reminder_email",
            self.booking,
            task_name="booking-reminder-email",
        )


@pytest.mark.parametrize(
    ("startdate", "starttime", "endtime", "expected_data"),
    [
        (
            "2023-10-10",
            "11:00",
            "12:00",
            {
                "startdate": "2023-10-10",
                "starttime": "11:00",
                "endtime": "12:00",
            },
        ),
        (
            "2023-10-10",
            None,
            "12:00",
            {
                "startdate": "2023-10-10",
                "starttime": "11:00",
                "endtime": "12:00",
            },
        ),
        (
            "2023-10-10",
            "11:00",
            None,
            {
                "startdate": "2023-10-10",
                "starttime": "11:00",
                "endtime": "12:00",
            },
        ),
        (
            None,
            "11:00",
            "12:00",
            {
                "startdate": "2023-10-10",
                "starttime": "11:00",
                "endtime": "12:00",
            },
        ),
        (
            None,
            None,
            None,
            {
                "startdate": "2023-10-10",
                "starttime": "11:00",
                "endtime": "12:00",
            },
        ),
    ],
)
@freeze_time(
    datetime.datetime(2023, 10, 10, 10, 0, 0).astimezone(
        tz=timezone.get_current_timezone()
    )
)
def test_set_initial_booking_data(startdate, starttime, endtime, expected_data):
    result = set_initial_booking_data(endtime, startdate, starttime, room=None)
    assert result == expected_data


class TestGetBookingStatus(TestCase):
    def setUp(self):
        self.room = RoomFactory()

        self.organization_group = OrganizationGroupFactory()
        self.organization_group.auto_confirmed_rooms.add(self.room)
        self.organization = OrganizationFactory()

        self.user = UserFactory()
        self.user_group = UserGroupFactory()
        self.user_group.auto_confirmed_rooms.add(self.room)

    def test_confirmed_by_organization(self):
        self.organization.organization_groups.add(self.organization_group)
        status = get_booking_status(self.user, self.organization, self.room)
        assert status == BookingStatus.CONFIRMED

    def test_pending_by_organization(self):
        status = get_booking_status(self.user, self.organization, self.room)
        assert status == BookingStatus.PENDING

    def test_confirmed_by_is_staff(self):
        self.user.is_staff = True
        status = get_booking_status(self.user, self.organization, self.room)
        assert status == BookingStatus.CONFIRMED

    def test_confirmed_by_usergroup(self):
        self.user_group.users.add(self.user)
        status = get_booking_status(self.user, self.organization, self.room)
        assert status == BookingStatus.CONFIRMED
