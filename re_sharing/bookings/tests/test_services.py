import datetime
import zoneinfo
from datetime import timedelta
from unittest import skip
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from dateutil.rrule import rrulestr
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingMessage
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services import InvalidBookingOperationError
from re_sharing.bookings.services import bookings_webview
from re_sharing.bookings.services import cancel_booking
from re_sharing.bookings.services import create_booking_data
from re_sharing.bookings.services import create_bookingmessage
from re_sharing.bookings.services import filter_bookings_list
from re_sharing.bookings.services import generate_booking
from re_sharing.bookings.services import get_booking_activity_stream
from re_sharing.bookings.services import is_bookable_by_organization
from re_sharing.bookings.services import manager_cancel_booking
from re_sharing.bookings.services import manager_confirm_booking
from re_sharing.bookings.services import manager_confirm_booking_series
from re_sharing.bookings.services import manager_filter_bookings_list
from re_sharing.bookings.services import manager_filter_invoice_bookings_list
from re_sharing.bookings.services import save_booking
from re_sharing.bookings.services import save_bookingmessage
from re_sharing.bookings.services import set_initial_booking_data
from re_sharing.bookings.services import show_booking
from re_sharing.bookings.services_booking_series import (
    cancel_bookings_of_booking_series,
)
from re_sharing.bookings.services_booking_series import (
    create_booking_series_and_bookings,
)
from re_sharing.bookings.services_booking_series import create_rrule
from re_sharing.bookings.services_booking_series import manager_cancel_booking_series
from re_sharing.bookings.services_booking_series import save_booking_series
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import AccessCodeFactory
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus

# Test constants
TEST_ATTENDEES_25 = 25
TEST_ATTENDEES_10 = 10
TEST_ATTENDEES_15 = 15
TEST_ATTENDEES_20 = 20
TEST_TOTAL_AMOUNT_100 = 100  # 2 hours * 50/hour
TEST_TOTAL_AMOUNT_225 = 225  # 3 hours * 75/hour


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
def test_cancel_bookings_of_booking_series():
    user = UserFactory()
    organization = OrganizationFactory()
    BookingPermissionFactory(
        user=user, organization=organization, status=BookingPermission.Status.CONFIRMED
    )

    booking_series = BookingSeriesFactory()
    booking1 = BookingFactory(
        user=user,
        organization=organization,
        booking_series=booking_series,
        start_date=timezone.now().date() - timedelta(days=5),
        status=BookingStatus.PENDING,
    )
    booking2 = BookingFactory(
        user=user,
        organization=organization,
        booking_series=booking_series,
        start_date=timezone.now().date() + timedelta(days=10),
        status=BookingStatus.PENDING,
    )
    booking3 = BookingFactory(
        user=user,
        organization=organization,
        booking_series=booking_series,
        start_date=timezone.now().date() + timedelta(days=5),
        status=BookingStatus.PENDING,
    )

    cancel_bookings_of_booking_series(user, booking_series.uuid)

    booking1.refresh_from_db()
    booking2.refresh_from_db()
    booking3.refresh_from_db()

    assert booking1.status == BookingStatus.PENDING
    assert booking2.status == BookingStatus.CANCELLED
    assert booking3.status == BookingStatus.CANCELLED


@skip
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

        bookingmessage = "Hello, but I still need a resource"
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
        self.resource = ResourceFactory(access=self.access)
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.start_datetime = timezone.now() + timedelta(days=6)
        self.booking = BookingFactory(
            organization=self.organization,
            status=BookingStatus.PENDING,
            resource=self.resource,
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
        # Using _() for translation, so we check that it contains the
        # key part of the message
        assert "only shown when confirmed" in str(access_code)

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
        # Using _() for translation, so we check that it contains the key
        # part of the message
        assert "only shown when confirmed" in str(access_code)

    def test_access_code_for_confirmed_booking(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        manager_confirm_booking(self.user, self.booking.slug)
        booking, activity_stream, access_code = show_booking(
            self.user, self.booking.slug
        )
        assert str(access_code) == str(self.access_code.code)

    def test_access_code_for_confirmed_booking_but_not_yet_shown(self):
        self.start_datetime = timezone.now() + timedelta(days=8)
        self.booking = BookingFactory(
            organization=self.organization,
            status=BookingStatus.PENDING,
            resource=self.resource,
            timespan=(self.start_datetime, self.start_datetime + timedelta(hours=2)),
        )
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        manager_confirm_booking(self.user, self.booking.slug)
        booking, activity_stream, access_code = show_booking(
            self.user, self.booking.slug
        )
        # Using _() for translation, so we check that it contains the key
        # part of the message
        assert "only shown 7 days before booking" in str(access_code)


class TestSaveBooking(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.resource = ResourceFactory()
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

    def test_save_booking_comprehensive_setup(self):
        # Test with more comprehensive setup including resource and compensation
        resource = ResourceFactory(is_private=True)
        compensation = CompensationFactory()
        organization_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(organization_group)
        organization_group.bookable_private_resources.add(resource)
        compensation.organization_groups.add(organization_group)

        # Ensure user has proper booking permission for this organization
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        booking = BookingFactory(
            user=self.user,
            organization=self.organization,
            resource=resource,
            compensation=compensation,
            status=BookingStatus.PENDING,
        )

        booking.status = BookingStatus.CONFIRMED
        saved_booking = save_booking(self.user, booking)

        assert saved_booking.status == BookingStatus.CONFIRMED


class TestCreateBookingMessage(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
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
        text_message = "I need a resource!"
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
@pytest.mark.parametrize(
    (
        "show_past_bookings",
        "organization",
        "status",
        "hide_recurring_bookings",
        "resource",
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
@pytest.mark.django_db()
def test_manger_filter_bookings_list(  # noqa: PLR0913
    show_past_bookings,
    organization,
    status,
    hide_recurring_bookings,
    resource,
    date_string,
    expected,
):
    """
    Test the 'filter_bookings_list' function
    """
    # Arrange
    user = UserFactory()
    org = OrganizationFactory(name="org")
    org_group = OrganizationGroupFactory()
    manager = ManagerFactory(user=user)
    org.organization_groups.add(org_group)
    manager.organization_groups.add(org_group)
    res = ResourceFactory()
    manager.resources.add(res)

    BookingFactory(
        user=user,
        organization=org,
        status=BookingStatus.PENDING,
        resource=res,
        timespan=(
            timezone.now() + timezone.timedelta(days=1),
            timezone.now() + timezone.timedelta(days=1, hours=1),
        ),
    )
    BookingFactory(
        user=user,
        organization=org,
        resource=res,
        timespan=(
            timezone.now() - timezone.timedelta(days=1, hours=2),
            timezone.now() - timezone.timedelta(days=1),
        ),
    )
    # Act
    bookings, organizations, resources = manager_filter_bookings_list(
        organization,
        show_past_bookings,
        status,
        hide_recurring_bookings,
        resource,
        date_string,
        user,
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
def test_create_rrule(rrule_data, expected):
    result = create_rrule(rrule_data)
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
        self.resource = ResourceFactory()
        self.compensation = CompensationFactory(
            hourly_rate=50, resource=[self.resource]
        )
        self.start_datetime = timezone.now() + timedelta(days=1)
        self.duration = 2
        self.invoice_address = "Fast lane 2, 929 Free-City"
        self.end_datetime = self.start_datetime + timedelta(hours=self.duration)
        self.booking_data = {
            "user": self.user.slug,
            "title": "Meeting",
            "resource": self.resource.slug,
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
            "invoice_address": self.invoice_address,
            "activity_description": "Simple Meeting",
            "import_id": "",
        }

    def test_generate_single_booking_valid_data(self):
        booking = generate_booking(self.booking_data)

        assert isinstance(booking, Booking)
        assert booking.user == self.user
        assert booking.title == "Meeting"
        assert booking.resource == self.resource
        assert booking.organization == self.organization
        assert booking.timespan == (self.start_datetime, self.end_datetime)
        assert booking.compensation == self.compensation
        assert booking.total_amount == self.compensation.hourly_rate * self.duration
        assert booking.activity_description == "Simple Meeting"
        assert booking.invoice_address == self.invoice_address

    def test_generate_single_booking_invalid_organization(self):
        self.booking_data["organization"] = "invalid-slug"

        with pytest.raises(Http404):
            generate_booking(self.booking_data)

    def test_generate_single_booking_invalid_resource(self):
        self.booking_data["resource"] = "invalid-slug"

        with pytest.raises(Http404):
            generate_booking(self.booking_data)

    def test_generate_single_booking_invalid_user(self):
        self.booking_data["user"] = "invalid-slug"

        with pytest.raises(Http404):
            generate_booking(self.booking_data)


class TestGenerateRecurrence(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
        self.compensation = CompensationFactory(hourly_rate=50)
        self.duration = 2
        self.start = (timezone.now() + timedelta(days=1) - timedelta(hours=2)).replace(
            microsecond=0
        )
        self.dt_start = "DTSTART:" + self.start.strftime("%Y%m%dT%H%M%S") + "Z"
        self.end_datetime = (self.start + timedelta(hours=self.duration)).replace(
            microsecond=0
        )
        self.count = 5
        self.invoice_address = "Fast lane 2, 929 Free-City"
        self.rrule_string = self.dt_start + "\nFREQ=DAILY;COUNT=" + str(self.count)
        self.booking_data = {
            "user": self.user.slug,
            "title": "Recurring Meeting",
            "resource": self.resource.slug,
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
            "invoice_address": self.invoice_address,
            "activity_description": "Simple Meeting",
        }

    def test_generate_recurrence_valid_data(self):
        bookings, rrule, bookable = create_booking_series_and_bookings(
            self.booking_data
        )

        assert len(bookings) == self.count
        for booking in bookings:
            assert isinstance(booking, Booking)
            assert booking.user == self.user
            assert booking.title == "Recurring Meeting"
            assert booking.resource == self.resource
            assert booking.organization == self.organization
            assert booking.compensation == self.compensation
            assert booking.total_amount == self.compensation.hourly_rate * self.duration
            assert booking.invoice_address == self.invoice_address
            assert booking.activity_description == "Simple Meeting"

        assert isinstance(rrule, BookingSeries)
        rrule_occurrences = list(rrulestr(self.rrule_string))
        assert rrule.rrule == self.rrule_string
        assert rrule.first_booking_date == rrule_occurrences[0]
        assert rrule.last_booking_date == rrule_occurrences[-1]
        assert bookable is True

    def test_generate_recurrence_invalid_organization(self):
        self.booking_data["organization"] = "invalid-slug"

        with pytest.raises(Http404):
            create_booking_series_and_bookings(self.booking_data)

    def test_generate_recurrence_invalid_resource(self):
        self.booking_data["resource"] = "invalid-slug"

        with pytest.raises(Http404):
            create_booking_series_and_bookings(self.booking_data)

    def test_generate_recurrence_invalid_user(self):
        self.booking_data["user"] = "invalid-slug"

        with pytest.raises(Http404):
            create_booking_series_and_bookings(self.booking_data)


class TestSaveBookingSeries(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
        self.compensation = CompensationFactory(hourly_rate=50)
        self.start = timezone.now() + timedelta(days=1) - timedelta(hours=2)
        self.end = self.start + timedelta(hours=2)
        dtstart_string = self.start.strftime("%Y%m%dT%H%M00Z")
        self.rrule_string = f"DTSTART:{dtstart_string}\nFREQ=DAILY;COUNT=5"
        self.booking_data = {
            "user": self.user.slug,
            "title": "Recurring Meeting",
            "resource": self.resource.slug,
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
            "invoice_address": "",
            "activity_description": "Meeting with team members",
            "import_id": "",
        }

        (
            self.bookings,
            self.booking_series,
            self.bookable,
        ) = create_booking_series_and_bookings(self.booking_data)

    def test_save_booking_series_valid(self):
        # Add the booking permission for the user
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        bookings, booking_series = save_booking_series(
            self.user, self.bookings, self.booking_series
        )

        for booking in bookings:
            assert booking.booking_series == booking_series

    def test_save_recurrence_permission_denied(self):
        # Do not add the booking permission for the user
        another_user = UserFactory()

        with pytest.raises(PermissionDenied):
            save_booking_series(another_user, self.bookings, self.booking_series)


@pytest.mark.django_db()
@patch.object(Booking, "is_cancelable", return_value=True)
def test_manager_cancel_booking_series(mock_is_cancelable):
    user = UserFactory(is_staff=True)
    booking_series = BookingSeriesFactory()
    booking1 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.PENDING
    )
    booking2 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.PENDING
    )

    manager_cancel_booking_series(user, booking_series.uuid)

    booking1.refresh_from_db()
    assert booking1.status == BookingStatus.CANCELLED
    booking2.refresh_from_db()
    assert booking2.status == BookingStatus.CANCELLED


@pytest.mark.django_db()
@patch.object(Booking, "is_confirmable", return_value=True)
def test_manager_confirm_booking_series(mock_is_confirmable):
    user = UserFactory(is_staff=True)
    booking_series = BookingSeriesFactory()
    booking1 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.PENDING
    )
    booking2 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.PENDING
    )

    manager_confirm_booking_series(user, booking_series.uuid)

    booking1.refresh_from_db()
    assert booking1.status == BookingStatus.CONFIRMED
    booking2.refresh_from_db()
    assert booking2.status == BookingStatus.CONFIRMED


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
    result = set_initial_booking_data(
        startdate=startdate, starttime=starttime, endtime=endtime, resource=None
    )
    assert result == expected_data


class TestIsBookableByOrganization(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.resource = ResourceFactory(
            is_private=True
        )  # Make resource private for better testing
        self.compensation = CompensationFactory()
        self.organization_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(self.organization_group)
        self.organization_group.bookable_private_resources.add(self.resource)
        self.compensation.organization_groups.add(self.organization_group)
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

    def test_staff_user_can_book_anything(self):
        self.user.is_staff = True
        assert is_bookable_by_organization(
            self.user, self.organization, self.resource, self.compensation
        )

    def test_unconfirmed_organization_cannot_book(self):
        self.organization.status = Organization.Status.PENDING
        self.organization.save()
        assert not is_bookable_by_organization(
            self.user, self.organization, self.resource, self.compensation
        )

    def test_user_without_booking_permission_cannot_book(self):
        BookingPermission.objects.filter(
            user=self.user, organization=self.organization
        ).delete()
        assert not is_bookable_by_organization(
            self.user, self.organization, self.resource, self.compensation
        )

    def test_confirmed_user_with_bookable_resource_can_book(self):
        assert is_bookable_by_organization(
            self.user, self.organization, self.resource, self.compensation
        )

    def test_resource_not_bookable_by_organization(self):
        # Remove the resource from organization group's bookable resources
        self.organization_group.bookable_private_resources.remove(self.resource)
        # Also need to ensure the resource isn't auto-confirmed
        self.organization_group.auto_confirmed_resources.clear()
        assert not is_bookable_by_organization(
            self.user, self.organization, self.resource, self.compensation
        )

    def test_compensation_not_bookable_by_organization(self):
        # Create a different organization group that the compensation belongs to
        # but the organization doesn't belong to
        different_group = OrganizationGroupFactory()
        self.compensation.organization_groups.clear()
        self.compensation.organization_groups.add(different_group)
        assert not is_bookable_by_organization(
            self.user, self.organization, self.resource, self.compensation
        )


class TestBookingsWebview(TestCase):
    def setUp(self):
        self.room_resource = ResourceFactory(type=Resource.ResourceTypeChoices.ROOM)
        self.parking_resource = ResourceFactory(
            type=Resource.ResourceTypeChoices.PARKING_LOT
        )

    def test_bookings_webview_with_date(self):
        from datetime import date

        test_date = date(2023, 12, 15)
        date_string = "2023-12-15"

        # Create confirmed room booking on test date
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 15, 10, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 15, 12, 0)),
            ),
        )

        # Create parking booking (should be excluded)
        BookingFactory(
            resource=self.parking_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 15, 10, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 15, 12, 0)),
            ),
        )

        # Create room booking on different date (should be excluded)
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 14, 10, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 14, 12, 0)),
            ),
        )

        bookings, shown_date, accesses = bookings_webview(date_string)

        assert bookings.count() == 1
        assert bookings.first().resource == self.room_resource
        assert shown_date == test_date

    def test_bookings_webview_without_date(self):
        today = timezone.now().date()

        from datetime import time

        # Create booking for today
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(10, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(12, 0))),
            ),
        )

        bookings, shown_date, accesses = bookings_webview(None)

        assert bookings.count() == 1
        assert shown_date == today

    def test_bookings_webview_only_confirmed(self):
        date_string = "2023-12-15"

        # Create confirmed booking
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 15, 10, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 15, 12, 0)),
            ),
        )

        # Create pending booking (should be excluded)
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.PENDING,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 15, 14, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 15, 16, 0)),
            ),
        )

        bookings, shown_date, accesses = bookings_webview(date_string)

        assert bookings.count() == 1
        assert bookings.first().status == BookingStatus.CONFIRMED

    def test_bookings_webview_access_filter(self):
        from re_sharing.resources.tests.factories import AccessFactory

        date_string = "2023-12-15"

        # Create two different accesses
        access1 = AccessFactory(name="Key Card")
        access2 = AccessFactory(name="Digital Code")

        # Create resources with different accesses
        resource_with_access1 = ResourceFactory(
            type=Resource.ResourceTypeChoices.ROOM, access=access1
        )
        resource_with_access2 = ResourceFactory(
            type=Resource.ResourceTypeChoices.ROOM, access=access2
        )

        # Create bookings for both resources
        BookingFactory(
            resource=resource_with_access1,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 15, 10, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 15, 12, 0)),
            ),
        )
        BookingFactory(
            resource=resource_with_access2,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2023, 12, 15, 14, 0)),
                timezone.make_aware(timezone.datetime(2023, 12, 15, 16, 0)),
            ),
        )

        # Test filtering by specific access
        bookings, shown_date, accesses = bookings_webview(date_string, access1.slug)

        assert bookings.count() == 1
        assert bookings.first().resource == resource_with_access1
        assert access1 in accesses
        assert access2 in accesses

        # Test filtering by another access
        bookings, shown_date, accesses = bookings_webview(date_string, access2.slug)

        assert bookings.count() == 1
        assert bookings.first().resource == resource_with_access2

        # Test "all" filter shows both bookings
        bookings, shown_date, accesses = bookings_webview(date_string, "all")

        assert bookings.count() == 2  # noqa: PLR2004


@pytest.mark.django_db()
@freeze_time(
    datetime.datetime(2023, 10, 10, 10, 0, 0).astimezone(
        tz=timezone.get_current_timezone()
    )
)
def test_set_initial_booking_data_with_all_parameters():
    """Test set_initial_booking_data with all optional parameters"""
    resource = ResourceFactory()
    organization = OrganizationFactory()

    result = set_initial_booking_data(
        startdate="2023-10-15",
        starttime="14:00",
        endtime="16:00",
        resource=resource.slug,
        organization=organization.slug,
        title="Test Title",
        activity_description="Test Description",
        attendees=25,
        import_id="IMPORT-123",
    )

    assert result["startdate"] == "2023-10-15"
    assert result["starttime"] == "14:00"
    assert result["endtime"] == "16:00"
    assert result["resource"] == resource
    assert result["organization"] == organization
    assert result["title"] == "Test Title"
    assert result["activity_description"] == "Test Description"
    assert result["number_of_attendees"] == TEST_ATTENDEES_25
    assert result["import_id"] == "IMPORT-123"


class TestCreateBookingData(TestCase):
    """Test create_booking_data function"""

    def test_create_booking_data_without_rrule(self):
        """Test creating booking data without recurring rule"""
        from unittest.mock import Mock

        user = UserFactory()
        resource = ResourceFactory()
        organization = OrganizationFactory()
        compensation = CompensationFactory()

        # Create mock form with cleaned_data
        form = Mock()
        start_dt = datetime.datetime(2023, 10, 15, 10, 0, tzinfo=datetime.UTC)
        end_dt = datetime.datetime(2023, 10, 15, 12, 0, tzinfo=datetime.UTC)

        form.cleaned_data = {
            "title": "Test Booking",
            "resource": resource,
            "timespan": (start_dt, end_dt),
            "organization": organization,
            "startdate": datetime.date(2023, 10, 15),
            "enddate": datetime.date(2023, 10, 15),
            "starttime": datetime.time(10, 0),
            "endtime": datetime.time(12, 0),
            "compensation": compensation,
            "invoice_address": "Test Address",
            "activity_description": "Test Activity",
            "number_of_attendees": 10,
            "rrule_repetitions": "NO_REPETITIONS",
        }

        booking_data, rrule = create_booking_data(user, form)

        assert booking_data["title"] == "Test Booking"
        assert booking_data["resource"] == resource.slug
        assert booking_data["organization"] == organization.slug
        assert booking_data["user"] == user.slug
        assert booking_data["compensation"] == compensation.id
        assert booking_data["invoice_address"] == "Test Address"
        assert booking_data["activity_description"] == "Test Activity"
        assert booking_data["number_of_attendees"] == TEST_ATTENDEES_10
        assert rrule is None


class TestGenerateBooking(TestCase):
    """Test generate_booking function"""

    def test_generate_booking_creates_new_booking(self):
        """Test generating a new booking"""
        user = UserFactory()
        resource = ResourceFactory()
        organization = OrganizationFactory()
        compensation = CompensationFactory(hourly_rate=50)

        start_dt = datetime.datetime(2023, 10, 15, 10, 0, tzinfo=datetime.UTC)
        end_dt = datetime.datetime(2023, 10, 15, 12, 0, tzinfo=datetime.UTC)

        booking_data = {
            "title": "New Booking",
            "resource": resource.slug,
            "timespan": (start_dt.isoformat(), end_dt.isoformat()),
            "organization": organization.slug,
            "start_date": "2023-10-15",
            "end_date": "2023-10-15",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "user": user.slug,
            "compensation": compensation.id,
            "invoice_address": "Test Address",
            "activity_description": "Test Activity",
            "number_of_attendees": TEST_ATTENDEES_15,
        }

        booking = generate_booking(booking_data)

        assert booking.title == "New Booking"
        assert booking.user == user
        assert booking.resource == resource
        assert booking.organization == organization
        assert booking.compensation == compensation
        assert booking.invoice_address == "Test Address"
        assert booking.activity_description == "Test Activity"
        assert booking.number_of_attendees == TEST_ATTENDEES_15
        assert booking.total_amount == TEST_TOTAL_AMOUNT_100

    def test_generate_booking_updates_existing_booking(self):
        """Test updating an existing booking"""
        user = UserFactory()
        resource = ResourceFactory()
        organization = OrganizationFactory()
        compensation = CompensationFactory(hourly_rate=75)

        # Create existing booking
        existing_booking = BookingFactory(
            user=user,
            resource=resource,
            organization=organization,
            title="Old Title",
            number_of_attendees=5,
        )

        # Update booking
        new_start = datetime.datetime(2023, 10, 16, 14, 0, tzinfo=datetime.UTC)
        new_end = datetime.datetime(2023, 10, 16, 17, 0, tzinfo=datetime.UTC)

        booking_data = {
            "booking_id": existing_booking.id,
            "title": "Updated Booking",
            "resource": resource.slug,
            "timespan": (new_start.isoformat(), new_end.isoformat()),
            "organization": organization.slug,
            "start_date": "2023-10-16",
            "end_date": "2023-10-16",
            "start_time": "14:00:00",
            "end_time": "17:00:00",
            "user": user.slug,
            "compensation": compensation.id,
            "invoice_address": "Updated Address",
            "activity_description": "Updated Activity",
            "number_of_attendees": TEST_ATTENDEES_20,
        }

        booking = generate_booking(booking_data)

        assert booking.id == existing_booking.id
        assert booking.title == "Updated Booking"
        assert booking.number_of_attendees == TEST_ATTENDEES_20
        assert booking.invoice_address == "Updated Address"
        assert booking.activity_description == "Updated Activity"
        assert booking.total_amount == TEST_TOTAL_AMOUNT_225

    def test_generate_booking_with_null_hourly_rate(self):
        """Test generating booking with compensation that has no hourly rate"""
        user = UserFactory()
        resource = ResourceFactory()
        organization = OrganizationFactory()
        compensation = CompensationFactory(hourly_rate=None)

        start_dt = datetime.datetime(2023, 10, 15, 10, 0, tzinfo=datetime.UTC)
        end_dt = datetime.datetime(2023, 10, 15, 12, 0, tzinfo=datetime.UTC)

        booking_data = {
            "title": "Free Booking",
            "resource": resource.slug,
            "timespan": (start_dt.isoformat(), end_dt.isoformat()),
            "organization": organization.slug,
            "start_date": "2023-10-15",
            "end_date": "2023-10-15",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "user": user.slug,
            "compensation": compensation.id,
            "invoice_address": "Test Address",
            "activity_description": "Free Activity",
            "number_of_attendees": 10,
        }

        booking = generate_booking(booking_data)

        assert booking.total_amount is None


class TestIsBookableByOrganizationManager(TestCase):
    """Test is_bookable_by_organization for manager users"""

    def test_manager_user_can_book_anything(self):
        """Test that manager users can book any combination"""
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)
        organization = OrganizationFactory()
        resource = ResourceFactory()
        compensation = CompensationFactory()

        result = is_bookable_by_organization(
            manager_user, organization, resource, compensation
        )

        assert result is True


class TestSaveBookingPermissionDenied(TestCase):
    """Test save_booking permission denied scenarios"""

    def test_save_booking_with_non_bookable_combination(self):
        """Test save_booking raises PermissionDenied for non-bookable combo"""
        user = UserFactory()
        organization = OrganizationFactory(status=0)  # Unconfirmed
        resource = ResourceFactory()
        compensation = CompensationFactory()

        booking = BookingFactory(
            user=user,
            organization=organization,
            resource=resource,
            compensation=compensation,
            status=BookingStatus.PENDING,
        )

        with pytest.raises(PermissionDenied):
            save_booking(user, booking)


class TestShowBookingAccessCode(TestCase):
    """Test show_booking access code scenarios"""

    def test_access_code_not_necessary_for_no_access_resource(self):
        """Test that access code is 'not necessary' when resource has no access"""
        user = UserFactory()
        organization = OrganizationFactory()
        BookingPermissionFactory(user=user, organization=organization, status=2)

        resource = ResourceFactory()
        # Don't create any Access for this resource

        booking = BookingFactory(
            user=user,
            organization=organization,
            resource=resource,
            status=BookingStatus.CONFIRMED,
        )

        result_booking, activity_stream, access_code = show_booking(user, booking.slug)

        assert access_code == "not necessary"


class TestManagerFilterBookingsListExtended(TestCase):
    """Test manager_filter_bookings_list with additional filters"""

    def test_filter_by_resource(self):
        """Test filtering bookings by resource"""
        manager_user = UserFactory()
        manager = ManagerFactory(user=manager_user)

        resource1 = ResourceFactory()
        resource2 = ResourceFactory()

        # Add resources to manager
        manager.resources.add(resource1, resource2)

        # Create organization group and add to manager
        org_group = OrganizationGroupFactory()
        manager.organization_groups.add(org_group)

        organization = OrganizationFactory()
        organization.organization_groups.add(org_group)

        BookingFactory(
            resource=resource1,
            organization=organization,
            status=BookingStatus.CONFIRMED,
        )
        BookingFactory(
            resource=resource2,
            organization=organization,
            status=BookingStatus.CONFIRMED,
        )

        bookings, _, _ = manager_filter_bookings_list(
            organization="all",
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=True,
            resource=resource1.slug,
            date_string=None,
            user=manager_user,
        )

        assert bookings.filter(resource=resource1).exists()
        assert bookings.count() >= 1

    def test_filter_hide_recurring_bookings(self):
        """Test filtering out recurring bookings"""
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)

        booking_series = BookingSeriesFactory()
        BookingFactory(booking_series=booking_series, status=BookingStatus.CONFIRMED)
        BookingFactory(booking_series=None, status=BookingStatus.CONFIRMED)

        bookings, _, _ = manager_filter_bookings_list(
            organization="all",
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=False,
            resource="all",
            date_string=None,
            user=manager_user,
        )

        assert not bookings.filter(booking_series__isnull=False).exists()

    def test_filter_by_date(self):
        """Test filtering bookings by specific date"""
        manager_user = UserFactory()
        manager = ManagerFactory(user=manager_user)

        resource = ResourceFactory()
        organization = OrganizationFactory()

        # Add resource to manager
        manager.resources.add(resource)

        # Create organization group and add to manager and organization
        org_group = OrganizationGroupFactory()
        manager.organization_groups.add(org_group)
        organization.organization_groups.add(org_group)

        specific_date = timezone.now().date()
        start_dt = timezone.make_aware(
            datetime.datetime.combine(specific_date, datetime.time(10, 0))
        )
        end_dt = timezone.make_aware(
            datetime.datetime.combine(specific_date, datetime.time(12, 0))
        )

        from psycopg.types.range import Range

        BookingFactory(
            resource=resource,
            organization=organization,
            timespan=Range(start_dt, end_dt),
            start_date=specific_date,
            status=BookingStatus.CONFIRMED,
        )

        bookings, _, _ = manager_filter_bookings_list(
            organization="all",
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=True,
            resource="all",
            date_string=specific_date.isoformat(),
            user=manager_user,
        )

        assert bookings.count() >= 1


class TestManagerCancelBookingError(TestCase):
    """Test manager_cancel_booking error scenarios"""

    def test_cancel_non_cancelable_booking_raises_error(self):
        """Test canceling non-cancelable booking raises error"""
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)

        # Create a booking that's already cancelled (not cancelable)
        booking = BookingFactory(status=BookingStatus.CANCELLED)

        with pytest.raises(InvalidBookingOperationError):
            manager_cancel_booking(manager_user, booking.slug)


class TestManagerConfirmBookingError(TestCase):
    """Test manager_confirm_booking error scenarios"""

    def test_confirm_non_confirmable_booking_raises_error(self):
        """Test confirming non-confirmable booking raises error"""
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)

        # Create a booking that's already confirmed (not confirmable)
        booking = BookingFactory(status=BookingStatus.CONFIRMED)

        with pytest.raises(InvalidBookingOperationError):
            manager_confirm_booking(manager_user, booking.slug)


class TestManagerFilterInvoiceBookingsList(TestCase):
    """Test manager_filter_invoice_bookings_list function"""

    def test_filter_invoice_bookings_all(self):
        """Test getting all invoice bookings"""
        BookingFactory(
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-001",
        )
        BookingFactory(
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="",
        )

        bookings, organizations, resources = manager_filter_invoice_bookings_list(
            organization="all",
            invoice_filter="all",
            invoice_number=None,
            resource="all",
        )

        expected_min_count = 2
        assert bookings.count() >= expected_min_count
        assert organizations.exists()
        assert resources.exists()

    def test_filter_invoice_bookings_with_invoice(self):
        """Test filtering bookings that have invoice numbers"""
        resource = ResourceFactory()
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-001",
        )
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="",
        )

        bookings, _, _ = manager_filter_invoice_bookings_list(
            organization="all",
            invoice_filter="with_invoice",
            invoice_number=None,
            resource="all",
        )

        assert bookings.filter(invoice_number="INV-001").exists()
        assert not bookings.filter(invoice_number="").exists()

    def test_filter_invoice_bookings_without_invoice(self):
        """Test filtering bookings that don't have invoice numbers"""
        resource = ResourceFactory()
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-001",
        )
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="",
        )

        bookings, _, _ = manager_filter_invoice_bookings_list(
            organization="all",
            invoice_filter="without_invoice",
            invoice_number=None,
            resource="all",
        )

        assert bookings.filter(invoice_number="").exists()
        assert not bookings.filter(invoice_number="INV-001").exists()

    def test_filter_invoice_bookings_by_organization(self):
        """Test filtering invoice bookings by organization"""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()

        BookingFactory(
            organization=org1,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
        )
        BookingFactory(
            organization=org2,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
        )

        bookings, _, _ = manager_filter_invoice_bookings_list(
            organization=org1.slug,
            invoice_filter="all",
            invoice_number=None,
            resource="all",
        )

        assert bookings.filter(organization=org1).exists()
        assert not bookings.filter(organization=org2).exists()

    def test_filter_invoice_bookings_by_invoice_number(self):
        """Test filtering invoice bookings by invoice number search"""
        BookingFactory(
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-2024-001",
        )
        BookingFactory(
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="INV-2025-002",
        )

        bookings, _, _ = manager_filter_invoice_bookings_list(
            organization="all",
            invoice_filter="all",
            invoice_number="2024",
            resource="all",
        )

        assert bookings.filter(invoice_number__icontains="2024").exists()

    def test_filter_invoice_bookings_by_resource(self):
        """Test filtering invoice bookings by resource"""
        resource1 = ResourceFactory()
        resource2 = ResourceFactory()

        BookingFactory(
            resource=resource1,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
        )
        BookingFactory(
            resource=resource2,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
        )

        bookings, _, _ = manager_filter_invoice_bookings_list(
            organization="all",
            invoice_filter="all",
            invoice_number=None,
            resource=resource1.slug,
        )

        assert bookings.filter(resource=resource1).exists()
        assert not bookings.filter(resource=resource2).exists()
