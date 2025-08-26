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
from re_sharing.bookings.services import create_bookingmessage
from re_sharing.bookings.services import filter_bookings_list
from re_sharing.bookings.services import generate_booking
from re_sharing.bookings.services import get_booking_activity_stream
from re_sharing.bookings.services import is_bookable_by_organization
from re_sharing.bookings.services import manager_cancel_booking
from re_sharing.bookings.services import manager_confirm_booking
from re_sharing.bookings.services import manager_confirm_booking_series
from re_sharing.bookings.services import manager_filter_bookings_list
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
@skip
def test_set_initial_booking_data(startdate, starttime, endtime, expected_data):
    result = set_initial_booking_data(endtime, startdate, starttime, resource=None)
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
