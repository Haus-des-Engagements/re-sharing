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
from psycopg.types.range import Range

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingMessage
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services import FreeBookingsExhaustedError
from re_sharing.bookings.services import InvalidBookingOperationError
from re_sharing.bookings.services import bookings_webview
from re_sharing.bookings.services import build_einvoice_payload
from re_sharing.bookings.services import build_invoice_payload
from re_sharing.bookings.services import build_org_einvoice_payload
from re_sharing.bookings.services import build_org_invoice_payload
from re_sharing.bookings.services import cancel_booking
from re_sharing.bookings.services import create_booking_data
from re_sharing.bookings.services import create_bookingmessage
from re_sharing.bookings.services import filter_bookings_list
from re_sharing.bookings.services import generate_booking
from re_sharing.bookings.services import get_booking_activity_stream
from re_sharing.bookings.services import get_external_events
from re_sharing.bookings.services import is_bookable_by_organization
from re_sharing.bookings.services import manager_cancel_booking
from re_sharing.bookings.services import manager_confirm_booking
from re_sharing.bookings.services import manager_confirm_booking_series
from re_sharing.bookings.services import manager_filter_bookings_list
from re_sharing.bookings.services import manager_filter_invoice_bookings_list
from re_sharing.bookings.services import needs_quota_reevaluation
from re_sharing.bookings.services import price_booking
from re_sharing.bookings.services import process_field_changes
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
from re_sharing.bookings.services_booking_series import extend_booking_series
from re_sharing.bookings.services_booking_series import generate_bookings
from re_sharing.bookings.services_booking_series import manager_cancel_booking_series
from re_sharing.bookings.services_booking_series import save_booking_series
from re_sharing.bookings.services_pricing import get_free_bookings_remaining_after
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.bookings.tests.helpers import patch_thread_pool
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import PermanentCodeFactory
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
TEST_EXPECTED_FUTURE_EVENTS = 2  # Number of future events in test ICS data
TEST_ORG_BOOKING_COUNT = 2  # Number of bookings in org invoice tests


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

    @patch("re_sharing.bookings.services._enqueue_smartlock_sync_if_today")
    def test_cancel_confirmed_booking_enqueues_smartlock_sync(self, mock_sync):
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

        mock_sync.assert_called_once()

    @patch("re_sharing.bookings.services._enqueue_smartlock_sync_if_today")
    def test_cancel_pending_booking_does_not_enqueue_smartlock_sync(self, mock_sync):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking.status = BookingStatus.PENDING
        start = timezone.now() + timedelta(days=1)
        self.booking.timespan = (start, start + timedelta(hours=2))
        self.booking.save()
        cancel_booking(self.user, self.booking.slug)

        mock_sync.assert_not_called()

    def _make_cancelable(self, booking):
        booking.status = BookingStatus.CONFIRMED
        start = timezone.now() + timedelta(days=1)
        booking.timespan = (start, start + timedelta(hours=2))
        booking.save()

    @patch("re_sharing.bookings.services.send_booking_cancellation_email")
    def test_manager_cancelling_other_users_booking_enqueues_email(self, mock_email):
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)  # no org groups -> can manage all orgs
        self._make_cancelable(self.booking)

        cancel_booking(manager_user, self.booking.slug)

        mock_email.enqueue.assert_called_once_with(self.booking.id)

    @patch("re_sharing.bookings.services.send_booking_cancellation_email")
    def test_user_cancelling_own_booking_does_not_enqueue_email(self, mock_email):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.booking.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self._make_cancelable(self.booking)

        cancel_booking(self.booking.user, self.booking.slug)

        mock_email.enqueue.assert_not_called()

    @patch("re_sharing.bookings.services.send_booking_cancellation_email")
    def test_manager_cancelling_own_booking_does_not_enqueue_email(self, mock_email):
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)
        booking = BookingFactory(organization=self.organization, user=manager_user)
        self._make_cancelable(booking)

        cancel_booking(manager_user, booking.slug)

        mock_email.enqueue.assert_not_called()

    @patch("re_sharing.bookings.services.send_booking_cancellation_email")
    def test_regular_user_cancelling_other_booking_does_not_enqueue_email(
        self, mock_email
    ):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        self._make_cancelable(self.booking)

        cancel_booking(self.user, self.booking.slug)

        mock_email.enqueue.assert_not_called()


@pytest.mark.django_db()
def test_cancel_bookings_of_booking_series():
    user = UserFactory()
    organization = OrganizationFactory()
    BookingPermissionFactory(
        user=user, organization=organization, status=BookingPermission.Status.CONFIRMED
    )

    booking_series = BookingSeriesFactory()
    # Past booking - should remain untouched
    booking_past = BookingFactory(
        user=user,
        organization=organization,
        booking_series=booking_series,
        start_date=timezone.now().date() - timedelta(days=5),
        status=BookingStatus.PENDING,
    )
    # Future bookings - should be deleted
    booking_future1 = BookingFactory(
        user=user,
        organization=organization,
        booking_series=booking_series,
        start_date=timezone.now().date() + timedelta(days=10),
        status=BookingStatus.PENDING,
    )
    booking_future2 = BookingFactory(
        user=user,
        organization=organization,
        booking_series=booking_series,
        start_date=timezone.now().date() + timedelta(days=5),
        status=BookingStatus.PENDING,
    )

    cancel_bookings_of_booking_series(user, booking_series.uuid)

    # Past booking stays, status unchanged
    booking_past.refresh_from_db()
    assert booking_past.status == BookingStatus.PENDING

    # Future bookings are deleted
    assert not Booking.objects.filter(id=booking_future1.id).exists()
    assert not Booking.objects.filter(id=booking_future2.id).exists()


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
        self.access_code = PermanentCodeFactory(
            accesses=[self.access],
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
        "organization_search",
        "status",
        "show_recurring_bookings",
        "resource",
        "location",
        "from_date_string",
        "until_date_string",
        "expected",
    ),
    [
        (True, None, "all", False, "all", "all", None, None, 2),
        (True, None, [1], False, "all", "all", None, None, 1),
        (False, None, "all", False, "all", "all", None, None, 1),
        (True, "org1", "all", False, "all", "all", None, None, 0),
    ],
)
@pytest.mark.django_db()
def test_manger_filter_bookings_list(  # noqa: PLR0913
    show_past_bookings,
    organization_search,
    status,
    show_recurring_bookings,
    resource,
    location,
    from_date_string,
    until_date_string,
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

    # Create standalone bookings (no booking_series) so they appear when
    # show_recurring_bookings=False (which excludes bookings with a series)
    BookingFactory(
        user=user,
        organization=org,
        status=BookingStatus.PENDING,
        resource=res,
        booking_series=None,
        timespan=(
            timezone.now() + timezone.timedelta(days=1),
            timezone.now() + timezone.timedelta(days=1, hours=1),
        ),
    )
    BookingFactory(
        user=user,
        organization=org,
        resource=res,
        booking_series=None,
        timespan=(
            timezone.now() - timezone.timedelta(days=1, hours=2),
            timezone.now() - timezone.timedelta(days=1),
        ),
    )
    # Act
    bookings, resources, locations = manager_filter_bookings_list(
        organization_search,
        show_past_bookings,
        status,
        show_recurring_bookings,
        resource,
        location,
        from_date_string,
        until_date_string,
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
        bookings, rrule, bookable, _pricing = create_booking_series_and_bookings(
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
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
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
            self.pricing,
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
        booking_series=booking_series,
        status=BookingStatus.PENDING,
        start_date=(timezone.now().date() - timedelta(weeks=1)),
    )
    booking2 = BookingFactory(
        booking_series=booking_series,
        start_date=(timezone.now().date() + timedelta(weeks=1)),
        status=BookingStatus.PENDING,
    )

    manager_cancel_booking_series(user, booking_series.uuid)

    booking1.refresh_from_db()
    assert booking1.status == BookingStatus.CANCELLED
    with pytest.raises(Booking.DoesNotExist):
        Booking.objects.get(id=booking2.id)


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


@pytest.mark.django_db()
@patch.object(Booking, "is_confirmable", return_value=True)
def test_manager_confirm_booking_series_preserves_cancelled_bookings(
    mock_is_confirmable,
):
    """Test that cancelled bookings in a series remain cancelled after confirmation"""
    user = UserFactory(is_staff=True)
    booking_series = BookingSeriesFactory()
    booking1 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.PENDING
    )
    booking2 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.CANCELLED
    )
    booking3 = BookingFactory(
        booking_series=booking_series, status=BookingStatus.PENDING
    )

    manager_confirm_booking_series(user, booking_series.uuid)

    booking1.refresh_from_db()
    assert booking1.status == BookingStatus.CONFIRMED
    booking2.refresh_from_db()
    assert booking2.status == BookingStatus.CANCELLED  # Should remain cancelled
    booking3.refresh_from_db()
    assert booking3.status == BookingStatus.CONFIRMED


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

    def test_deactivated_organization_cannot_book(self):
        self.organization.status = Organization.Status.DEACTIVATED
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

    def test_bookings_webview_filters_by_today(self):
        from datetime import time

        today = timezone.now().date()

        # Create confirmed room booking for today
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(10, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(23, 59))),
            ),
        )

        # Create parking booking (should be excluded - wrong resource type)
        BookingFactory(
            resource=self.parking_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(10, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(23, 59))),
            ),
        )

        bookings, access = bookings_webview()

        assert bookings.count() == 1
        assert bookings.first().resource == self.room_resource

    def test_bookings_webview_only_confirmed(self):
        from datetime import time

        today = timezone.now().date()

        # Create confirmed booking
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(10, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(23, 59))),
            ),
        )

        # Create pending booking (should be excluded)
        BookingFactory(
            resource=self.room_resource,
            status=BookingStatus.PENDING,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(14, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(23, 59))),
            ),
        )

        bookings, access = bookings_webview()

        assert bookings.count() == 1
        assert bookings.first().status == BookingStatus.CONFIRMED

    def test_bookings_webview_location_filter(self):
        from datetime import time

        from re_sharing.resources.tests.factories import LocationFactory

        today = timezone.now().date()

        # Create two different locations
        location1 = LocationFactory(name="Building A")
        location2 = LocationFactory(name="Building B")

        # Create resources at different locations
        resource_at_location1 = ResourceFactory(
            type=Resource.ResourceTypeChoices.ROOM, location=location1
        )
        resource_at_location2 = ResourceFactory(
            type=Resource.ResourceTypeChoices.ROOM, location=location2
        )

        # Create bookings for both resources
        BookingFactory(
            resource=resource_at_location1,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(10, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(23, 59))),
            ),
        )
        BookingFactory(
            resource=resource_at_location2,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime.combine(today, time(14, 0))),
                timezone.make_aware(timezone.datetime.combine(today, time(23, 59))),
            ),
        )

        # Test filtering by specific location
        bookings, location = bookings_webview(location1.slug)

        assert bookings.count() == 1
        assert bookings.first().resource == resource_at_location1


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

        # Create standalone bookings so they appear when show_recurring_bookings=False
        BookingFactory(
            resource=resource1,
            organization=organization,
            booking_series=None,
            status=BookingStatus.CONFIRMED,
        )
        BookingFactory(
            resource=resource2,
            organization=organization,
            booking_series=None,
            status=BookingStatus.CONFIRMED,
        )

        bookings, _, _ = manager_filter_bookings_list(
            organization_search=None,
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=False,
            resource=resource1.slug,
            location="all",
            from_date_string=None,
            until_date_string=None,
            user=manager_user,
        )

        assert bookings.filter(resource=resource1).exists()
        assert bookings.count() >= 1

    def test_filter_show_only_recurring_bookings(self):
        """Test showing all bookings when show_recurring_bookings=True"""
        manager_user = UserFactory()
        manager = ManagerFactory(user=manager_user)

        # Setup organization group and resource for manager
        org_group = OrganizationGroupFactory()
        organization = OrganizationFactory()
        organization.organization_groups.add(org_group)
        manager.organization_groups.add(org_group)

        resource = ResourceFactory()
        manager.resources.add(resource)

        # Create one recurring booking and one standalone booking
        booking_series = BookingSeriesFactory(status=BookingStatus.CONFIRMED)
        BookingFactory(
            booking_series=booking_series,
            status=BookingStatus.CONFIRMED,
            organization=organization,
            resource=resource,
        )
        BookingFactory(
            booking_series=None,
            status=BookingStatus.CONFIRMED,
            organization=organization,
            resource=resource,
        )

        # When show_recurring_bookings=True, should show all bookings
        bookings, _, _ = manager_filter_bookings_list(
            organization_search=None,
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=True,
            resource="all",
            location="all",
            from_date_string=None,
            until_date_string=None,
            user=manager_user,
        )

        # Should contain both bookings
        assert bookings.count() == 2  # noqa: PLR2004
        assert bookings.filter(booking_series__isnull=False).exists()
        assert bookings.filter(booking_series__isnull=True).exists()

    def test_filter_show_confirmed_series_bookings(self):
        """
        Test showing only standalone bookings
        when show_recurring_bookings=False
        """
        manager_user = UserFactory()
        manager = ManagerFactory(user=manager_user)

        # Setup organization group and resource for manager
        org_group = OrganizationGroupFactory()
        organization = OrganizationFactory()
        organization.organization_groups.add(org_group)
        manager.organization_groups.add(org_group)

        resource = ResourceFactory()
        manager.resources.add(resource)

        # Create bookings with different series statuses and standalone
        confirmed_series = BookingSeriesFactory(status=BookingStatus.CONFIRMED)
        pending_series = BookingSeriesFactory(status=BookingStatus.PENDING)

        BookingFactory(
            booking_series=confirmed_series,
            status=BookingStatus.CONFIRMED,
            organization=organization,
            resource=resource,
        )
        BookingFactory(
            booking_series=pending_series,
            status=BookingStatus.CONFIRMED,
            organization=organization,
            resource=resource,
        )
        standalone_booking = BookingFactory(
            booking_series=None,
            status=BookingStatus.CONFIRMED,
            organization=organization,
            resource=resource,
        )

        # When show_recurring_bookings=False, should only show standalone bookings
        bookings, _, _ = manager_filter_bookings_list(
            organization_search=None,
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=False,
            resource="all",
            location="all",
            from_date_string=None,
            until_date_string=None,
            user=manager_user,
        )

        # Should only contain the standalone booking
        assert bookings.count() == 1
        assert standalone_booking in bookings

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

        # Create standalone booking so it appears when show_recurring_bookings=False
        BookingFactory(
            resource=resource,
            organization=organization,
            booking_series=None,
            timespan=Range(start_dt, end_dt),
            start_date=specific_date,
            status=BookingStatus.CONFIRMED,
        )

        bookings, _, _ = manager_filter_bookings_list(
            organization_search=None,
            show_past_bookings=True,
            status="all",
            show_recurring_bookings=False,
            resource="all",
            location="all",
            from_date_string=specific_date.isoformat(),
            until_date_string=specific_date.isoformat(),
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


class TestManagerConfirmBookingOverlap(TestCase):
    """Test manager_confirm_booking with overlapping bookings"""

    def setUp(self):
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.resource = ResourceFactory()
        self.organization = OrganizationFactory()

        # Create a confirmed booking from 10:00 to 12:00
        self.start_time = timezone.now() + timedelta(days=1)
        self.end_time = self.start_time + timedelta(hours=2)
        self.confirmed_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.CONFIRMED,
            timespan=(self.start_time, self.end_time),
        )

    def test_confirm_booking_with_overlap_sets_status_unavailable(self):
        """Test that confirming a booking with overlap sets status to UNAVAILABLE"""
        # Create a pending booking that overlaps (10:30 to 12:30)
        overlapping_start = self.start_time + timedelta(minutes=30)
        overlapping_end = self.end_time + timedelta(minutes=30)
        pending_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(overlapping_start, overlapping_end),
        )

        # Attempt to confirm the overlapping booking
        result = manager_confirm_booking(self.manager_user, pending_booking.slug)

        # Assert the booking status is UNAVAILABLE, not CONFIRMED
        assert result.status == BookingStatus.UNAVAILABLE
        result.refresh_from_db()
        assert result.status == BookingStatus.UNAVAILABLE

    def test_confirm_booking_without_overlap_sets_status_confirmed(self):
        """Test that confirming a booking without overlap sets status to CONFIRMED"""
        # Create a pending booking that does NOT overlap (13:00 to 15:00)
        non_overlapping_start = self.end_time + timedelta(hours=1)
        non_overlapping_end = non_overlapping_start + timedelta(hours=2)
        pending_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(non_overlapping_start, non_overlapping_end),
        )

        # Attempt to confirm the non-overlapping booking
        result = manager_confirm_booking(self.manager_user, pending_booking.slug)

        # Assert the booking status is CONFIRMED
        assert result.status == BookingStatus.CONFIRMED
        result.refresh_from_db()
        assert result.status == BookingStatus.CONFIRMED

    def test_confirm_booking_overlap_different_resource_sets_status_confirmed(
        self,
    ):
        """
        Test confirming a booking on different resource sets status to CONFIRMED
        """
        # Create a different resource
        different_resource = ResourceFactory()

        # Create a pending booking for different resource at same time
        pending_booking = BookingFactory(
            resource=different_resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(self.start_time, self.end_time),
        )

        # Attempt to confirm the booking on different resource
        result = manager_confirm_booking(self.manager_user, pending_booking.slug)

        # Assert the booking status is CONFIRMED (different resource = no overlap)
        assert result.status == BookingStatus.CONFIRMED
        result.refresh_from_db()
        assert result.status == BookingStatus.CONFIRMED

    def test_confirm_booking_partial_overlap_sets_status_unavailable(self):
        """Test that partial overlap also sets status to UNAVAILABLE"""
        # Create a pending booking with partial overlap (11:00 to 13:00)
        partial_overlap_start = self.start_time + timedelta(hours=1)
        partial_overlap_end = self.end_time + timedelta(hours=1)
        pending_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(partial_overlap_start, partial_overlap_end),
        )

        # Attempt to confirm the partially overlapping booking
        result = manager_confirm_booking(self.manager_user, pending_booking.slug)

        # Assert the booking status is UNAVAILABLE
        assert result.status == BookingStatus.UNAVAILABLE
        result.refresh_from_db()
        assert result.status == BookingStatus.UNAVAILABLE

    def test_confirm_booking_exact_overlap_sets_status_unavailable(self):
        """Test that exact overlap sets status to UNAVAILABLE"""
        # Create a pending booking with exact same timespan
        exact_overlap_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(self.start_time, self.end_time),
        )

        # Attempt to confirm the exactly overlapping booking
        result = manager_confirm_booking(self.manager_user, exact_overlap_booking.slug)

        # Assert the booking status is UNAVAILABLE
        assert result.status == BookingStatus.UNAVAILABLE
        result.refresh_from_db()
        assert result.status == BookingStatus.UNAVAILABLE

    def test_confirm_booking_contained_overlap_sets_status_unavailable(self):
        """
        Test booking contained within confirmed booking
        sets status to UNAVAILABLE
        """
        # Create pending booking contained within confirmed booking
        contained_start = self.start_time + timedelta(minutes=30)
        contained_end = self.end_time - timedelta(minutes=30)
        pending_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(contained_start, contained_end),
        )

        # Attempt to confirm the contained booking
        result = manager_confirm_booking(self.manager_user, pending_booking.slug)

        # Assert the booking status is UNAVAILABLE
        assert result.status == BookingStatus.UNAVAILABLE
        result.refresh_from_db()
        assert result.status == BookingStatus.UNAVAILABLE

    def test_confirm_booking_overlap_with_cancelled_sets_status_confirmed(self):
        """Test that overlap with cancelled booking still allows confirmation"""
        # Change the existing booking to CANCELLED
        self.confirmed_booking.status = BookingStatus.CANCELLED
        self.confirmed_booking.save()

        # Create a pending booking that overlaps
        overlapping_start = self.start_time + timedelta(minutes=30)
        overlapping_end = self.end_time + timedelta(minutes=30)
        pending_booking = BookingFactory(
            resource=self.resource,
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(overlapping_start, overlapping_end),
        )

        # Attempt to confirm - should succeed since other booking is cancelled
        result = manager_confirm_booking(self.manager_user, pending_booking.slug)

        # Assert the booking status is CONFIRMED
        assert result.status == BookingStatus.CONFIRMED
        result.refresh_from_db()
        assert result.status == BookingStatus.CONFIRMED


class TestManagerFilterInvoiceBookingsList(TestCase):
    """Test manager_filter_invoice_bookings_list function"""

    def setUp(self):
        # manager_filter_invoice_bookings_list defaults to timespan_filter
        # "past", but BookingFactory picks a random start_date that reaches
        # 300 days into the future. Every booking here is therefore pinned to
        # its own past slot: distinct days also keep confirmed bookings on a
        # shared resource from tripping exclude_overlapping_reservations.
        self._past_slot = 0

    def _past_booking(self, **kwargs):
        self._past_slot += 1
        ends_at = timezone.now() - timedelta(days=self._past_slot)
        kwargs.setdefault("timespan", (ends_at - timedelta(hours=2), ends_at))
        return BookingFactory(**kwargs)

    def test_filter_invoice_bookings_all(self):
        """Test getting all invoice bookings"""
        self._past_booking(
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-001",
        )
        self._past_booking(
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="",
        )

        bookings, resources = manager_filter_invoice_bookings_list(
            organization_search=None,
            invoice_filter="all",
            invoice_number=None,
            resource="all",
        )

        expected_min_count = 2
        assert bookings.count() >= expected_min_count
        assert resources.exists()

    def test_filter_invoice_bookings_with_invoice(self):
        """Test filtering bookings that have invoice numbers"""
        resource = ResourceFactory()
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-001",
        )
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="",
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=None,
            invoice_filter="with_invoice",
            invoice_number=None,
            resource="all",
        )

        assert bookings.filter(invoice_number="INV-001").exists()
        assert not bookings.filter(invoice_number="").exists()

    def test_filter_invoice_bookings_without_invoice(self):
        """Test filtering bookings that don't have invoice numbers"""
        resource = ResourceFactory()
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-001",
        )
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="",
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=None,
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

        self._past_booking(
            organization=org1,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
        )
        self._past_booking(
            organization=org2,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=org1.name,
            invoice_filter="all",
            invoice_number=None,
            resource="all",
        )

        assert bookings.filter(organization=org1).exists()
        assert not bookings.filter(organization=org2).exists()

    def test_filter_invoice_bookings_by_invoice_number(self):
        """Test filtering invoice bookings by invoice number search"""
        self._past_booking(
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_number="INV-2024-001",
        )
        self._past_booking(
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_number="INV-2025-002",
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=None,
            invoice_filter="all",
            invoice_number="2024",
            resource="all",
        )

        assert bookings.filter(invoice_number__icontains="2024").exists()

    def test_filter_invoice_bookings_by_resource(self):
        """Test filtering invoice bookings by resource"""
        resource1 = ResourceFactory()
        resource2 = ResourceFactory()

        self._past_booking(
            resource=resource1,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
        )
        self._past_booking(
            resource=resource2,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=None,
            invoice_filter="all",
            invoice_number=None,
            resource=resource1.slug,
        )

        assert bookings.filter(resource=resource1).exists()
        assert not bookings.filter(resource=resource2).exists()

    def test_filter_invoice_bookings_with_invoice_address(self):
        """Test filtering bookings that have an invoice address"""
        resource = ResourceFactory()
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_address={
                "company_name": "Test GmbH",
                "street": "Teststr. 1",
                "zip_code": "79100",
                "city": "Freiburg",
                "email": "t@t.de",
            },
        )
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_address={},
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=None,
            invoice_filter="all",
            invoice_number=None,
            resource="all",
            invoice_address_filter="with_address",
        )

        assert bookings.filter(invoice_address__has_key="company_name").exists()
        assert not bookings.filter(invoice_address={}).exists()

    def test_filter_invoice_bookings_without_invoice_address(self):
        """Test filtering bookings that don't have an invoice address"""
        resource = ResourceFactory()
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=100,
            invoice_address={
                "company_name": "Test GmbH",
                "street": "Teststr. 1",
                "zip_code": "79100",
                "city": "Freiburg",
                "email": "t@t.de",
            },
        )
        self._past_booking(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            total_amount=200,
            invoice_address={},
        )

        bookings, _ = manager_filter_invoice_bookings_list(
            organization_search=None,
            invoice_filter="all",
            invoice_number=None,
            resource="all",
            invoice_address_filter="without_address",
        )

        assert bookings.filter(invoice_address={}).exists()
        assert not bookings.filter(invoice_address__has_key="company_name").exists()


class TestDeletedEntityHandling(TestCase):
    """Test that deleted entities are handled gracefully in activity stream."""

    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
        self.compensation = CompensationFactory()
        self.booking = BookingFactory(
            user=self.user,
            organization=self.organization,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.PENDING,
        )

    def test_process_field_changes_with_deleted_user(self):
        """Test that process_field_changes handles deleted users gracefully."""
        user2 = UserFactory()
        user_id = user2.id

        # Delete the user
        user2.delete()

        # Process field change with deleted user
        changes = process_field_changes("user", (str(self.user.id), str(user_id)))

        assert changes["field"] == "User"
        assert changes["old_value"] == f"{self.user.first_name} {self.user.last_name}"
        assert changes["new_value"] == "(deleted)"

    def test_process_field_changes_with_deleted_resource(self):
        """Test that process_field_changes handles deleted resources gracefully."""
        resource2 = ResourceFactory()
        resource_id = resource2.id

        # Delete the resource
        resource2.delete()

        # Process field change with deleted resource
        changes = process_field_changes(
            "resource", (str(self.resource.id), str(resource_id))
        )

        assert changes["field"] == "Resource"
        assert changes["old_value"] == self.resource.name
        assert changes["new_value"] == "(deleted)"

    def test_process_field_changes_with_deleted_compensation(self):
        """Test that process_field_changes handles deleted compensations gracefully."""
        compensation2 = CompensationFactory()
        compensation_id = compensation2.id

        # Delete the compensation
        compensation2.delete()

        # Process field change with deleted compensation
        changes = process_field_changes(
            "compensation", (str(self.compensation.id), str(compensation_id))
        )

        assert changes["field"] == "Compensation"
        assert changes["old_value"] == self.compensation.name
        assert changes["new_value"] == "(deleted)"

    def test_process_field_changes_with_deleted_organization(self):
        """Test that process_field_changes handles deleted organizations gracefully."""
        organization2 = OrganizationFactory()
        organization_id = organization2.id

        # Delete the organization
        organization2.delete()

        # Process field change with deleted organization
        changes = process_field_changes(
            "organization", (str(self.organization.id), str(organization_id))
        )

        assert changes["field"] == "Organization"
        assert changes["old_value"] == self.organization.name
        assert changes["new_value"] == "(deleted)"

    def test_get_booking_activity_stream_with_deleted_actor(self):
        """Test that activity stream handles deleted actor gracefully."""
        from auditlog.context import set_actor

        # Create a user who will be deleted
        actor = UserFactory()

        # Make a change to the booking with the actor
        with set_actor(actor):
            self.booking.title = "Updated Title"
            self.booking.save()

        # Delete the actor
        actor.delete()

        # Get activity stream - should not raise an error
        activity_stream = get_booking_activity_stream(self.booking)

        # Find the change entry
        change_entry = None
        for entry in activity_stream:
            if entry["type"] == "change":
                change_entry = entry
                break

        # Verify that the user is None for deleted actor
        assert change_entry is not None
        assert change_entry["user"] is None


class TestGetExternalEvents(TestCase):
    """Test get_external_events function for ICS feed parsing"""

    def setUp(self):
        # get_external_events drops events that start before today, so these
        # dates are relative: hard-coded ones silently turn the whole class
        # red once they pass.
        today = timezone.now().date()
        self.first_future = today + timedelta(days=30)
        self.second_future = today + timedelta(days=60)
        past = today - timedelta(days=365)
        self.sample_ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test Calendar//EN
BEGIN:VEVENT
DTSTART:{self.first_future:%Y%m%d}T100000Z
DTEND:{self.first_future:%Y%m%d}T120000Z
SUMMARY:Future Event 1
LOCATION:Conference Room A
DESCRIPTION:A test event in the future
URL:https://example.com/event1
END:VEVENT
BEGIN:VEVENT
DTSTART:{self.second_future:%Y%m%d}T140000Z
DTEND:{self.second_future:%Y%m%d}T160000Z
SUMMARY:Future Event 2
LOCATION:Conference Room B
DESCRIPTION:Another future event
END:VEVENT
BEGIN:VEVENT
DTSTART:{past:%Y%m%d}T100000Z
DTEND:{past:%Y%m%d}T120000Z
SUMMARY:Past Event
LOCATION:Old Room
DESCRIPTION:This event is in the past
END:VEVENT
END:VCALENDAR""".encode()

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_parses_ics_feed_correctly(self, mock_get, mock_cache):
        """Test that ICS feed is parsed correctly"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = self.sample_ics
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_events"
        )

        # Should have 2 future events (past event filtered out)
        assert len(events) == TEST_EXPECTED_FUTURE_EVENTS
        assert events[0]["title"] == "Future Event 1"
        assert events[0]["location"] == "Conference Room A"
        assert events[0]["description"] == "A test event in the future"
        assert events[1]["title"] == "Future Event 2"

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_filters_past_events(self, mock_get, mock_cache):
        """Test that past events are filtered out"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = self.sample_ics
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_filter"
        )

        # Verify no past events
        for event in events:
            assert event["title"] != "Past Event"

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_sorts_events_by_start_date(self, mock_get, mock_cache):
        """Test that events are sorted by start date"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = self.sample_ics
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_sort"
        )

        # Check that events are sorted by start date
        if len(events) >= TEST_EXPECTED_FUTURE_EVENTS:
            assert events[0]["start"] <= events[1]["start"]

    @patch("django.core.cache.cache")
    def test_returns_cached_events(self, mock_cache):
        """Test that cached events are returned without fetching"""
        cached_events = [
            {"title": "Cached Event", "start": timezone.now(), "end": None}
        ]
        mock_cache.get.return_value = cached_events

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_cached"
        )

        assert events == cached_events
        mock_cache.get.assert_called_once_with("test_cached")

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_caches_fetched_events(self, mock_get, mock_cache):
        """Test that fetched events are cached for 24 hours"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = self.sample_ics
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        get_external_events(
            "https://example.com/events.ics", cache_key="test_cache_set"
        )

        # Verify cache.set was called with 24 hour TTL (86400 seconds)
        mock_cache.set.assert_called_once()
        args = mock_cache.set.call_args[0]
        assert args[0] == "test_cache_set"  # cache key
        assert args[2] == 60 * 60 * 24  # 24 hours in seconds

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_handles_request_error_gracefully(self, mock_get, mock_cache):
        """Test that request errors are handled gracefully"""
        import requests

        mock_cache.get.return_value = None
        mock_get.side_effect = requests.RequestException("Connection failed")

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_error"
        )

        # Should return empty list on error
        assert events == []

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_handles_invalid_ics_gracefully(self, mock_get, mock_cache):
        """Test that invalid ICS content is handled gracefully"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = b"This is not valid ICS content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_invalid"
        )

        # Should return empty list for invalid content
        assert events == []

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_handles_empty_calendar(self, mock_get, mock_cache):
        """Test that empty calendar is handled correctly"""
        empty_ics = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test Calendar//EN
END:VCALENDAR"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = empty_ics
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_empty"
        )

        assert events == []

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_handles_event_without_dtstart(self, mock_get, mock_cache):
        """Test that events without DTSTART are skipped"""
        ics_no_dtstart = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test Calendar//EN
BEGIN:VEVENT
SUMMARY:Event without start
DESCRIPTION:This event has no start date
END:VEVENT
BEGIN:VEVENT
DTSTART:20270401T100000Z
DTEND:20270401T120000Z
SUMMARY:Valid Event
END:VEVENT
END:VCALENDAR"""
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = ics_no_dtstart
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_no_dtstart"
        )

        # Only the valid event should be included
        assert len(events) == 1
        assert events[0]["title"] == "Valid Event"

    @patch("django.core.cache.cache")
    @patch("requests.get")
    def test_handles_all_day_events(self, mock_get, mock_cache):
        """Test that all-day events (date only) are handled correctly"""
        all_day = timezone.now().date() + timedelta(days=30)
        ics_all_day = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test Calendar//EN
BEGIN:VEVENT
DTSTART;VALUE=DATE:{all_day:%Y%m%d}
DTEND;VALUE=DATE:{all_day + timedelta(days=1):%Y%m%d}
SUMMARY:All Day Event
END:VEVENT
END:VCALENDAR""".encode()
        mock_cache.get.return_value = None
        mock_response = Mock()
        mock_response.content = ics_all_day
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        events = get_external_events(
            "https://example.com/events.ics", cache_key="test_all_day"
        )

        assert len(events) == 1
        assert events[0]["title"] == "All Day Event"


class TestCreateItemBookingGroup(TestCase):
    """Tests for create_item_booking_group service."""

    def setUp(self):
        from datetime import time

        from re_sharing.bookings.services_item_bookings import create_item_booking_group
        from re_sharing.providers.models import LendingTimeSlot
        from re_sharing.resources.models import Resource

        self.create_item_booking_group = create_item_booking_group

        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        # is_private=False (default) so any organization can book it
        self.resource = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=5,
        )

        # No organization_groups on compensation → bookable by all organizations
        self.compensation = CompensationFactory(daily_rate=10)
        self.compensation.resource.add(self.resource)

        # Monday pickup, Tuesday return
        LendingTimeSlot.objects.create(
            slot_type=LendingTimeSlot.SlotType.PICKUP,
            weekday=0,
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        LendingTimeSlot.objects.create(
            slot_type=LendingTimeSlot.SlotType.RETURN,
            weekday=1,
            start_time=time(14, 0),
            end_time=time(16, 0),
        )

        # Next Monday and Tuesday
        today = timezone.now().date()
        days_until_monday = (7 - today.weekday()) % 7 or 7
        self.pickup_date = today + datetime.timedelta(days=days_until_monday)
        self.return_date = self.pickup_date + datetime.timedelta(days=1)

    def test_booking_group_is_confirmed_immediately(self):
        """Item booking groups are confirmed without manager approval."""

        booking_group = self.create_item_booking_group(
            user=self.user,
            organization=self.organization,
            pickup_date=self.pickup_date,
            return_date=self.return_date,
            items=[{"resource_id": self.resource.pk, "quantity": 1}],
        )

        assert booking_group.status == BookingStatus.CONFIRMED

    def test_individual_bookings_are_confirmed_immediately(self):
        """Each booking within the group is confirmed without manager approval."""
        booking_group = self.create_item_booking_group(
            user=self.user,
            organization=self.organization,
            pickup_date=self.pickup_date,
            return_date=self.return_date,
            items=[{"resource_id": self.resource.pk, "quantity": 2}],
        )

        bookings = booking_group.bookings_of_bookinggroup.all()
        assert bookings.count() == 1
        assert bookings.first().status == BookingStatus.CONFIRMED

    def test_no_booking_permission_raises(self):
        """Users without booking permission cannot create item bookings."""
        from django.core.exceptions import PermissionDenied

        other_user = UserFactory()
        with pytest.raises(PermissionDenied):
            self.create_item_booking_group(
                user=other_user,
                organization=self.organization,
                pickup_date=self.pickup_date,
                return_date=self.return_date,
                items=[{"resource_id": self.resource.pk, "quantity": 1}],
            )

    def test_manager_can_book_for_any_organization(self):
        """Managers can create item bookings for organizations they don't belong to."""
        from re_sharing.providers.tests.factories import ManagerFactory

        manager_user = UserFactory()
        ManagerFactory(user=manager_user)
        # manager_user has NO BookingPermission for self.organization

        booking_group = self.create_item_booking_group(
            user=manager_user,
            organization=self.organization,
            pickup_date=self.pickup_date,
            return_date=self.return_date,
            items=[{"resource_id": self.resource.pk, "quantity": 1}],
        )

        assert booking_group.status == BookingStatus.CONFIRMED

    def test_regular_user_cannot_book_private_item(self):
        """Regular users cannot book private lendable items."""
        from django.core.exceptions import ValidationError

        from re_sharing.resources.models import Resource

        private_resource = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=5,
            is_private=True,
        )
        self.compensation.resource.add(private_resource)

        regular_user = UserFactory()
        BookingPermissionFactory(
            user=regular_user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        with pytest.raises(ValidationError):
            self.create_item_booking_group(
                user=regular_user,
                organization=self.organization,
                pickup_date=self.pickup_date,
                return_date=self.return_date,
                items=[{"resource_id": private_resource.pk, "quantity": 1}],
            )

    def test_manager_can_book_private_item(self):
        """Managers can book private lendable items."""
        from re_sharing.providers.tests.factories import ManagerFactory
        from re_sharing.resources.models import Resource

        private_resource = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=5,
            is_private=True,
        )
        self.compensation.resource.add(private_resource)

        manager_user = UserFactory()
        ManagerFactory(user=manager_user)
        BookingPermissionFactory(
            user=manager_user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        booking_group = self.create_item_booking_group(
            user=manager_user,
            organization=self.organization,
            pickup_date=self.pickup_date,
            return_date=self.return_date,
            items=[{"resource_id": private_resource.pk, "quantity": 1}],
        )
        assert booking_group.status == BookingStatus.CONFIRMED


class TestOrganizationCanBookItems(TestCase):
    """Tests for organization_can_book_items eligibility check."""

    def setUp(self):
        from re_sharing.bookings.services_item_bookings import (
            ITEM_BOOKING_ELIGIBLE_GROUP_IDS,
        )

        self.eligible_ids = ITEM_BOOKING_ELIGIBLE_GROUP_IDS

    def test_organization_in_any_eligible_group_can_book(self):
        from re_sharing.bookings.services_item_bookings import (
            organization_can_book_items,
        )

        for eligible_id in self.eligible_ids:
            with self.subTest(eligible_id=eligible_id):
                organization = OrganizationFactory()
                group = OrganizationGroupFactory(pk=eligible_id)
                organization.organization_groups.add(group)

                assert organization_can_book_items(organization) is True

    def test_organization_without_eligible_group_cannot_book(self):
        from re_sharing.bookings.services_item_bookings import (
            organization_can_book_items,
        )

        organization = OrganizationFactory()
        other_pk = max(self.eligible_ids) + 100
        group = OrganizationGroupFactory(pk=other_pk)
        organization.organization_groups.add(group)

        assert organization_can_book_items(organization) is False


class TestBuildInvoicePayload(TestCase):
    """Test build_invoice_payload function"""

    def setUp(self):
        self.organization = OrganizationFactory(
            name="Test Organisation e.V.",
            street_and_housenb="Teststraße 1",
            zip_code="79100",
            city="Freiburg",
            email="test@example.com",
        )
        self.user = UserFactory(first_name="Max", last_name="Mustermann")
        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 1, 15, 16, 0, tzinfo=tz)
        end = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=tz)
        self.booking = BookingFactory(
            organization=self.organization,
            user=self.user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            timespan=Range(start, end),
            start_date=start.date(),
            end_date=end.date(),
            start_time=start.time(),
            end_time=end.time(),
        )

    def test_builds_payload_with_correct_company_data(self):
        payload = build_invoice_payload(self.booking)

        assert payload["company_name"] == "Test Organisation e.V."
        assert payload["street"] == "Teststraße 1"
        assert payload["zip"] == "79100"
        assert payload["city"] == "Freiburg"
        assert payload["email"] == "test@example.com"
        assert payload["contact_person_name"] == "Max Mustermann"
        assert payload["buyer_reference"] == "0"

    def test_builds_payload_with_correct_item_data(self):
        payload = build_invoice_payload(self.booking)

        assert len(payload["item_name"]) == 1
        assert "Veranstaltungsraum" in payload["item_name"][0]
        assert "15.01.2026" in payload["item_name"][0]
        assert "16:00" in payload["item_name"][0]
        assert "19:00" in payload["item_name"][0]
        assert payload["item_amount"] == ["3"]
        assert payload["item_unit"] == ["Std."]
        assert payload["item_single_price"] == ["12"]
        assert payload["item_vat"] == ["0"]

    def test_builds_payload_with_fractional_hours(self):
        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 1, 15, 16, 0, tzinfo=tz)
        end = datetime.datetime(2026, 1, 15, 18, 30, tzinfo=tz)
        self.booking.timespan = Range(start, end)
        self.booking.save()

        payload = build_invoice_payload(self.booking)

        assert payload["item_amount"] == ["2.5"]

    def test_builds_payload_with_correct_meta_fields(self):
        payload = build_invoice_payload(self.booking)

        assert payload["type"] == "invoice"
        assert payload["show_prices_type"] == "gross"
        assert payload["due_days"] == "14"
        assert payload["show_bankdata"] is True
        assert payload["show_contactdata"] is True
        assert payload["date_of_supply"] == "15.01.2026"

    def test_uses_invoice_address_when_set(self):
        self.booking.invoice_address = {
            "company_name": "Other Company GmbH",
            "street": "Andere Straße 5",
            "zip_code": "79098",
            "city": "Freiburg",
            "email": "billing@other.com",
        }
        self.booking.save()

        payload = build_invoice_payload(self.booking)

        assert payload["company_name"] == "Other Company GmbH"
        assert payload["street"] == "Andere Straße 5"
        assert payload["zip"] == "79098"
        assert payload["city"] == "Freiburg"
        assert payload["email"] == "billing@other.com"
        assert payload["buyer_reference"] == "0"

    def test_uses_invoice_address_with_buyer_reference(self):
        self.booking.invoice_address = {
            "company_name": "Stadtverwaltung Freiburg",
            "street": "Rathausplatz 1",
            "zip_code": "79098",
            "city": "Freiburg",
            "email": "rechnung@freiburg.de",
            "buyer_reference": "991-12345-67",
        }
        self.booking.save()

        payload = build_invoice_payload(self.booking)

        assert payload["company_name"] == "Stadtverwaltung Freiburg"
        assert payload["buyer_reference"] == "991-12345-67"

    def test_ignores_old_complete_invoice_address_key(self):
        self.booking.invoice_address = {
            "old_complete_invoice_address": "Some old freetext address",
        }
        self.booking.save()

        payload = build_invoice_payload(self.booking)

        # Should fall back to organization data when structured fields missing
        assert payload["company_name"] == "Test Organisation e.V."
        assert payload["street"] == "Teststraße 1"

    def test_item_single_price_derived_from_total_amount(self):
        """item_single_price always uses total_amount/duration, ignoring hourly_rate."""
        self.booking.total_amount = 45
        self.booking.save()

        payload = build_invoice_payload(self.booking)

        # 45 / 3h = 15, regardless of compensation.hourly_rate=12
        assert payload["item_single_price"] == ["15"]

    def test_uneven_division_falls_back_to_lump_sum(self):
        """When total_amount/duration is not a clean 2-decimal price, use one
        lump-sum line so BuchhaltungsButler accepts it and the total stays exact."""
        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        end = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=tz)  # 7 hours
        self.booking.timespan = Range(start, end)
        self.booking.total_amount = 450  # 450 / 7 = 64.2857... -> not clean
        self.booking.save()

        payload = build_invoice_payload(self.booking)

        assert payload["item_amount"] == ["1"]
        assert payload["item_unit"] == ["Pauschale"]
        assert payload["item_single_price"] == ["450"]


class TestBuildEinvoicePayload(TestCase):
    """Test build_einvoice_payload function"""

    def setUp(self):
        self.organization = OrganizationFactory(
            name="Test Organisation e.V.",
            street_and_housenb="Teststraße 1",
            zip_code="79100",
            city="Freiburg",
            email="test@example.com",
        )
        self.user = UserFactory(first_name="Max", last_name="Mustermann")
        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 1, 15, 16, 0, tzinfo=tz)
        end = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=tz)
        self.booking = BookingFactory(
            organization=self.organization,
            user=self.user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            timespan=Range(start, end),
            start_date=start.date(),
            end_date=end.date(),
            start_time=start.time(),
            end_time=end.time(),
        )

    def test_builds_payload_with_einvoice_fields(self):
        payload = build_einvoice_payload(self.booking)

        assert payload["item_tax_type"] == ["E"]
        assert payload["item_tax_amount"] == ["0"]
        assert payload["e_invoice_id"] == "0"
        assert payload["country"] == "DE"
        assert payload["show_bankdata"] is True
        assert payload["show_contactdata"] is True
        assert payload["street"] == "Teststraße 1"
        assert payload["zip"] == "79100"
        assert payload["city"] == "Freiburg"

    def test_builds_payload_with_correct_item_data(self):
        payload = build_einvoice_payload(self.booking)

        assert "Veranstaltungsraum" in payload["item_name"][0]
        assert "15.01.2026" in payload["item_name"][0]
        assert "16:00" in payload["item_name"][0]
        assert "19:00" in payload["item_name"][0]
        assert payload["item_amount"] == ["3"]
        assert payload["item_single_price"] == ["12"]

    def test_builds_payload_with_fractional_hours(self):
        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 1, 15, 16, 0, tzinfo=tz)
        end = datetime.datetime(2026, 1, 15, 18, 30, tzinfo=tz)
        self.booking.timespan = Range(start, end)
        self.booking.save()

        payload = build_einvoice_payload(self.booking)

        assert payload["item_amount"] == ["2.5"]

    def test_uses_invoice_address_with_buyer_reference(self):
        self.booking.invoice_address = {
            "company_name": "Stadtverwaltung Freiburg",
            "street": "Rathausplatz 1",
            "zip_code": "79098",
            "city": "Freiburg",
            "email": "rechnung@freiburg.de",
            "buyer_reference": "991-12345-67",
        }
        self.booking.save()

        payload = build_einvoice_payload(self.booking)

        assert payload["company_name"] == "Stadtverwaltung Freiburg"
        assert payload["e_invoice_id"] == "991-12345-67"
        assert payload["street"] == "Rathausplatz 1"
        assert payload["email"] == "rechnung@freiburg.de"

    def test_e_invoice_id_defaults_to_zero(self):
        self.booking.invoice_address = {
            "company_name": "Some Company",
            "street": "Street 1",
            "zip_code": "12345",
            "city": "Berlin",
            "email": "a@b.com",
        }
        self.booking.save()

        payload = build_einvoice_payload(self.booking)

        assert payload["e_invoice_id"] == "0"

    def test_item_single_price_derived_from_total_amount(self):
        """item_single_price always uses total_amount/duration, ignoring hourly_rate."""
        self.booking.total_amount = 45
        self.booking.save()

        payload = build_einvoice_payload(self.booking)

        # 45 / 3h = 15, regardless of compensation.hourly_rate=12
        assert payload["item_single_price"] == ["15"]

    def test_uneven_division_falls_back_to_lump_sum(self):
        """Uneven prices collapse to one lump-sum line for BuchhaltungsButler."""
        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        end = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=tz)  # 7 hours
        self.booking.timespan = Range(start, end)
        self.booking.total_amount = 450  # 450 / 7 = 64.2857... -> not clean
        self.booking.save()

        payload = build_einvoice_payload(self.booking)

        assert payload["item_amount"] == ["1"]
        assert payload["item_unit"] == ["Pauschale"]
        assert payload["item_single_price"] == ["450"]


class TestBuildOrgInvoicePayload(TestCase):
    """Test build_org_invoice_payload function"""

    def setUp(self):
        self.organization = OrganizationFactory(
            name="Test Organisation e.V.",
            street_and_housenb="Teststraße 1",
            zip_code="79100",
            city="Freiburg",
            email="test@example.com",
        )
        self.user = UserFactory(first_name="Max", last_name="Mustermann")
        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start1 = datetime.datetime(2026, 1, 15, 16, 0, tzinfo=tz)
        end1 = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=tz)
        self.booking1 = BookingFactory(
            organization=self.organization,
            user=self.user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            invoice_number="",
            timespan=Range(start1, end1),
            start_date=start1.date(),
            end_date=end1.date(),
            start_time=start1.time(),
            end_time=end1.time(),
        )

        start2 = datetime.datetime(2026, 1, 20, 10, 0, tzinfo=tz)
        end2 = datetime.datetime(2026, 1, 20, 12, 30, tzinfo=tz)
        self.booking2 = BookingFactory(
            organization=self.organization,
            user=self.user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=30,
            invoice_number="",
            timespan=Range(start2, end2),
            start_date=start2.date(),
            end_date=end2.date(),
            start_time=start2.time(),
            end_time=end2.time(),
        )

    def test_builds_payload_with_multiple_items(self):
        bookings = [self.booking1, self.booking2]
        payload = build_org_invoice_payload(self.organization, bookings)

        assert len(payload["item_name"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_amount"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_unit"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_vat"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_single_price"]) == TEST_ORG_BOOKING_COUNT

    def test_each_item_has_correct_data(self):
        bookings = [self.booking1, self.booking2]
        payload = build_org_invoice_payload(self.organization, bookings)

        assert "15.01.2026" in payload["item_name"][0]
        assert "16:00" in payload["item_name"][0]
        assert "19:00" in payload["item_name"][0]
        assert payload["item_amount"][0] == "3"

        assert "20.01.2026" in payload["item_name"][1]
        assert "10:00" in payload["item_name"][1]
        assert "12:30" in payload["item_name"][1]
        assert payload["item_amount"][1] == "2.5"

    def test_uses_organization_address(self):
        bookings = [self.booking1]
        payload = build_org_invoice_payload(self.organization, bookings)

        assert payload["company_name"] == "Test Organisation e.V."
        assert payload["street"] == "Teststraße 1"
        assert payload["zip"] == "79100"
        assert payload["city"] == "Freiburg"
        assert payload["email"] == "test@example.com"

    def test_uses_earliest_date_of_supply(self):
        bookings = [self.booking1, self.booking2]
        payload = build_org_invoice_payload(self.organization, bookings)

        assert payload["date_of_supply"] == "15.01.2026"

    def test_meta_fields(self):
        bookings = [self.booking1]
        payload = build_org_invoice_payload(self.organization, bookings)

        assert payload["type"] == "invoice"
        assert payload["show_prices_type"] == "gross"
        assert payload["due_days"] == "14"
        assert payload["show_bankdata"] is True
        assert payload["show_contactdata"] is True

    def test_items_ordered_by_date(self):
        bookings = [self.booking2, self.booking1]
        payload = build_org_invoice_payload(self.organization, bookings)

        # Should be ordered by date regardless of input order
        assert "15.01.2026" in payload["item_name"][0]
        assert "20.01.2026" in payload["item_name"][1]

    def test_item_single_price_derived_from_total_amount(self):
        """item_single_price always uses total_amount/duration, ignoring hourly_rate."""
        self.booking1.total_amount = 45  # 3h -> 15/h
        self.booking1.save()
        self.booking2.total_amount = 50  # 2.5h -> 20/h
        self.booking2.save()

        payload = build_org_invoice_payload(
            self.organization, [self.booking1, self.booking2]
        )

        assert payload["item_single_price"] == ["15", "20"]


class TestBuildOrgEinvoicePayload(TestCase):
    """Test build_org_einvoice_payload function"""

    def setUp(self):
        self.organization = OrganizationFactory(
            name="Test Organisation e.V.",
            street_and_housenb="Teststraße 1",
            zip_code="79100",
            city="Freiburg",
            email="test@example.com",
        )
        self.user = UserFactory(first_name="Max", last_name="Mustermann")
        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start1 = datetime.datetime(2026, 1, 15, 16, 0, tzinfo=tz)
        end1 = datetime.datetime(2026, 1, 15, 19, 0, tzinfo=tz)
        self.booking1 = BookingFactory(
            organization=self.organization,
            user=self.user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            invoice_number="",
            timespan=Range(start1, end1),
            start_date=start1.date(),
            end_date=end1.date(),
            start_time=start1.time(),
            end_time=end1.time(),
        )

        start2 = datetime.datetime(2026, 1, 20, 10, 0, tzinfo=tz)
        end2 = datetime.datetime(2026, 1, 20, 12, 30, tzinfo=tz)
        self.booking2 = BookingFactory(
            organization=self.organization,
            user=self.user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=30,
            invoice_number="",
            timespan=Range(start2, end2),
            start_date=start2.date(),
            end_date=end2.date(),
            start_time=start2.time(),
            end_time=end2.time(),
        )

    def test_builds_payload_with_multiple_items(self):
        bookings = [self.booking1, self.booking2]
        payload = build_org_einvoice_payload(self.organization, bookings)

        assert len(payload["item_name"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_amount"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_tax_type"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_tax_amount"]) == TEST_ORG_BOOKING_COUNT
        assert len(payload["item_single_price"]) == TEST_ORG_BOOKING_COUNT

    def test_has_einvoice_specific_fields(self):
        bookings = [self.booking1]
        payload = build_org_einvoice_payload(self.organization, bookings)

        assert payload["item_tax_type"] == ["E"]
        assert payload["item_tax_amount"] == ["0"]
        assert payload["e_invoice_id"] == "0"
        assert payload["country"] == "DE"
        assert "item_vat" not in payload

    def test_uses_organization_address(self):
        bookings = [self.booking1]
        payload = build_org_einvoice_payload(self.organization, bookings)

        assert payload["company_name"] == "Test Organisation e.V."
        assert payload["street"] == "Teststraße 1"
        assert payload["zip"] == "79100"
        assert payload["city"] == "Freiburg"

    def test_items_ordered_by_date(self):
        bookings = [self.booking2, self.booking1]
        payload = build_org_einvoice_payload(self.organization, bookings)

        assert "15.01.2026" in payload["item_name"][0]
        assert "20.01.2026" in payload["item_name"][1]

    def test_item_single_price_derived_from_total_amount(self):
        """item_single_price always uses total_amount/duration, ignoring hourly_rate."""
        self.booking1.total_amount = 45  # 3h -> 15/h
        self.booking1.save()
        self.booking2.total_amount = 50  # 2.5h -> 20/h
        self.booking2.save()

        payload = build_org_einvoice_payload(
            self.organization, [self.booking1, self.booking2]
        )

        assert payload["item_single_price"] == ["15", "20"]


class TestManagerFilterBookingsListByAccessCode(TestCase):
    """
    Searching the manager booking list by access code returns exactly the
    bookings that display that code.

    `Booking.access_code` is populated by a default generator for every booking,
    so a stored match is not evidence the code is ever shown to anyone. Only
    bookings whose derived code (`get_access_code`) equals the search term may
    be returned.
    """

    def setUp(self):
        self.user = UserFactory()
        self.manager = ManagerFactory(user=self.user)
        self.organization_group = OrganizationGroupFactory()
        self.manager.organization_groups.add(self.organization_group)

        self.organization = OrganizationFactory(name="Managed Org")
        self.organization.organization_groups.add(self.organization_group)

        self.access_with_smartlock = AccessFactory(
            name="smartlock access", smartlock_id="smartlock-1"
        )
        self.access_without_smartlock = AccessFactory(
            name="plain access", smartlock_id=""
        )

        self.resource_smartlock = ResourceFactory(
            name="Smartlock Room", access=self.access_with_smartlock
        )
        self.resource_plain = ResourceFactory(
            name="Plain Room", access=self.access_without_smartlock
        )
        self.resource_without_access = ResourceFactory(
            name="No Access Room", access=None
        )
        self.manager.resources.add(
            self.resource_smartlock,
            self.resource_plain,
            self.resource_without_access,
        )

    def _make_booking(self, resource, organization=None, days=1, **kwargs):
        # Confirmed bookings on one resource may not overlap
        # (exclude_overlapping_reservations), so callers that need a second
        # booking on the same resource move it to another day.
        start = timezone.now() + timezone.timedelta(days=days)
        booking = BookingFactory(
            user=self.user,
            organization=organization or self.organization,
            resource=resource,
            booking_series=None,
            status=BookingStatus.CONFIRMED,
            timespan=(start, start + timezone.timedelta(hours=2)),
            **kwargs,
        )
        booking.refresh_from_db()
        return booking

    def _search(self, access_code, **overrides):
        params = {
            "organization_search": None,
            "show_past_bookings": True,
            "status": "all",
            "show_recurring_bookings": True,
            "resource": "all",
            "location": "all",
            "from_date_string": None,
            "until_date_string": None,
            "user": self.user,
            "access_code_search": access_code,
        }
        params.update(overrides)
        bookings, _resources, _locations = manager_filter_bookings_list(**params)
        return list(bookings)

    # --- matches -----------------------------------------------------------

    def test_finds_booking_by_its_own_access_code(self):
        booking = self._make_booking(self.resource_smartlock, access_code="345678")

        assert self._search("345678") == [booking]

    def test_finds_bookings_by_organization_permanent_code(self):
        PermanentCodeFactory(
            code="ORGCODE",
            organization=self.organization,
            validity_start=timezone.now() - timezone.timedelta(days=1),
            validity_end=None,
            accesses=[self.access_with_smartlock],
        )
        booking = self._make_booking(self.resource_smartlock)

        assert self._search("ORGCODE") == [booking]

    def test_finds_bookings_by_general_permanent_code(self):
        PermanentCodeFactory(
            code="GENERAL",
            organization=None,
            validity_start=timezone.now() - timezone.timedelta(days=1),
            validity_end=None,
            accesses=[self.access_without_smartlock],
        )
        booking = self._make_booking(self.resource_plain)

        assert self._search("GENERAL") == [booking]

    def test_general_code_does_not_return_bookings_shadowed_by_org_code(self):
        """An organization with its own code never displays the general one."""
        PermanentCodeFactory(
            code="GENERAL",
            organization=None,
            validity_start=timezone.now() - timezone.timedelta(days=1),
            validity_end=None,
            accesses=[self.access_without_smartlock],
        )
        PermanentCodeFactory(
            code="ORGCODE",
            organization=self.organization,
            validity_start=timezone.now() - timezone.timedelta(days=1),
            validity_end=None,
            accesses=[self.access_without_smartlock],
        )
        self._make_booking(self.resource_plain)

        assert self._search("GENERAL") == []

    def test_matches_the_trimmed_search_term(self):
        booking = self._make_booking(self.resource_smartlock, access_code="345678")

        assert self._search("  345678  ") == [booking]

    # --- phantoms ----------------------------------------------------------

    def test_stored_code_shadowed_by_org_permanent_code_is_not_returned(self):
        PermanentCodeFactory(
            code="ORGCODE",
            organization=self.organization,
            validity_start=timezone.now() - timezone.timedelta(days=1),
            validity_end=None,
            accesses=[self.access_with_smartlock],
        )
        self._make_booking(self.resource_smartlock, access_code="345678")

        assert self._search("345678") == []

    def test_stored_code_on_resource_without_smartlock_is_not_returned(self):
        self._make_booking(self.resource_plain, access_code="345678")

        assert self._search("345678") == []

    def test_stored_code_on_resource_without_access_is_not_returned(self):
        self._make_booking(self.resource_without_access, access_code="345678")

        assert self._search("345678") == []

    def test_expired_permanent_code_does_not_match_its_bookings(self):
        PermanentCodeFactory(
            code="EXPIRED",
            organization=self.organization,
            validity_start=timezone.now() - timezone.timedelta(days=10),
            validity_end=timezone.now() - timezone.timedelta(days=5),
            accesses=[self.access_with_smartlock],
        )
        self._make_booking(self.resource_smartlock, access_code="345678")

        assert self._search("EXPIRED") == []

    # --- blank and short input --------------------------------------------

    def test_empty_search_does_not_filter(self):
        booking = self._make_booking(self.resource_smartlock, access_code="")
        other = self._make_booking(
            self.resource_smartlock, days=2, access_code="345678"
        )

        assert set(self._search("")) == {booking, other}

    def test_none_search_does_not_filter(self):
        booking = self._make_booking(self.resource_smartlock, access_code="")

        assert self._search(None) == [booking]

    def test_whitespace_only_search_does_not_filter(self):
        booking = self._make_booking(self.resource_smartlock, access_code="")

        assert self._search("   ") == [booking]

    def test_too_short_search_does_not_filter(self):
        booking = self._make_booking(self.resource_smartlock, access_code="")
        other = self._make_booking(
            self.resource_smartlock, days=2, access_code="345678"
        )

        assert set(self._search("34")) == {booking, other}

    # --- ordering ----------------------------------------------------------

    def test_results_are_ordered_by_proximity_to_now(self):
        """A permanent code can be shared by bookings spread over months."""
        PermanentCodeFactory(
            code="ORGCODE",
            organization=self.organization,
            validity_start=timezone.now() - timezone.timedelta(days=60),
            validity_end=None,
            accesses=[self.access_with_smartlock],
        )
        far_future = self._make_booking(self.resource_smartlock, days=30)
        past = self._make_booking(self.resource_smartlock, days=-20)
        nearest = self._make_booking(self.resource_smartlock, days=1)

        assert self._search("ORGCODE") == [nearest, past, far_future]

    # --- manager scope -----------------------------------------------------

    def test_booking_of_unmanaged_organization_is_not_returned(self):
        other_group = OrganizationGroupFactory(name="other group")
        other_organization = OrganizationFactory(name="Other Org")
        other_organization.organization_groups.add(other_group)
        self._make_booking(
            self.resource_smartlock,
            organization=other_organization,
            access_code="345678",
        )

        assert self._search("345678") == []

    def test_booking_of_unmanaged_resource_is_not_returned(self):
        unmanaged_resource = ResourceFactory(
            name="Unmanaged Room", access=self.access_with_smartlock
        )
        self._make_booking(unmanaged_resource, access_code="345678")

        assert self._search("345678") == []


class FreeBookingsQuotaTestMixin:
    """A limited organization with a consuming and a paid compensation."""

    allowance = 2

    def set_up_quota(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.group = OrganizationGroupFactory(
            free_bookings_per_year=self.allowance,
            free_bookings_valid_from=datetime.date(2027, 1, 1),
        )
        self.organization.organization_groups.add(self.group)
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.resource = ResourceFactory()
        self.free_compensation = CompensationFactory(
            hourly_rate=None,
            counts_against_free_bookings=True,
            resource=[self.resource],
        )
        self.paid_compensation = CompensationFactory(
            hourly_rate=15, resource=[self.resource]
        )

    def unsaved_booking(self, start_date, hours=2, **kwargs):
        start = timezone.make_aware(
            datetime.datetime.combine(start_date, datetime.time(10))
        )
        end = start + datetime.timedelta(hours=hours)
        defaults = {
            "title": "Meeting",
            "organization": self.organization,
            "user": self.user,
            "resource": self.resource,
            "status": BookingStatus.CONFIRMED,
            "timespan": (start, end),
            "start_date": start_date,
            "end_date": start_date,
            "start_time": start.time(),
            "end_time": end.time(),
            "activity_description": "Meeting",
            "invoice_address": {},
        }
        defaults.update(kwargs)
        return Booking(**defaults)

    def use_free_bookings(self, count, year=2027):
        # every used booking gets its own day, so none overlap on the resource
        used = []
        for _ in range(count):
            self._used_days = getattr(self, "_used_days", 0) + 1
            used.append(
                BookingFactory(
                    title=f"used-{year}-{self._used_days}",
                    organization=self.organization,
                    resource=self.resource,
                    compensation=self.free_compensation,
                    start_date=datetime.date(year, 2, 1)
                    + datetime.timedelta(days=self._used_days),
                    status=BookingStatus.CONFIRMED,
                    uses_free_booking=True,
                )
            )
        return used


class TestPriceBooking(FreeBookingsQuotaTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()

    def test_free_booking_left(self):
        booking = self.unsaved_booking(datetime.date(2027, 3, 1), hours=3)

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is True
        assert booking.total_amount is None
        assert booking.compensation == self.free_compensation

    def test_last_free_booking(self):
        self.use_free_bookings(1)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is True

    def test_exhausted_with_fallback_is_fully_paid(self):
        self.use_free_bookings(2)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1), hours=2)

        price_booking(
            booking,
            self.free_compensation,
            fallback_compensation=self.paid_compensation,
        )

        assert booking.uses_free_booking is False
        assert booking.compensation == self.paid_compensation
        assert booking.total_amount == 30  # noqa: PLR2004

    def test_exhausted_without_fallback_raises(self):
        self.use_free_bookings(2)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))

        with pytest.raises(FreeBookingsExhaustedError) as excinfo:
            price_booking(booking, self.free_compensation)

        assert excinfo.value.year == 2027  # noqa: PLR2004

    def test_unlimited_organization_is_free_and_unflagged(self):
        self.organization.organization_groups.add(OrganizationGroupFactory())
        self.use_free_bookings(2)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is False
        assert booking.total_amount is None
        assert booking.compensation == self.free_compensation

    def test_non_consuming_compensation_is_priced_as_today(self):
        booking = self.unsaved_booking(datetime.date(2027, 3, 1), hours=2)

        price_booking(booking, self.paid_compensation)

        assert booking.uses_free_booking is False
        assert booking.total_amount == 30  # noqa: PLR2004

    def test_long_booking_uses_one_free_booking(self):
        self.use_free_bookings(1)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1), hours=8)

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is True
        assert booking.total_amount is None

    def test_quota_year_follows_the_start_date(self):
        self.use_free_bookings(2, year=2027)
        booking = self.unsaved_booking(datetime.date(2028, 1, 3))

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is True

    def test_booking_before_the_valid_from_date_is_not_limited(self):
        booking = self.unsaved_booking(datetime.date(2026, 12, 31))

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is False
        assert booking.total_amount is None

    def test_booking_on_the_valid_from_date_is_limited(self):
        booking = self.unsaved_booking(datetime.date(2027, 1, 1))

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is True

    def test_nothing_configured_keeps_pricing_unchanged(self):
        self.group.free_bookings_per_year = None
        self.group.free_bookings_valid_from = None
        self.group.save()
        self.free_compensation.counts_against_free_bookings = False
        self.free_compensation.save()
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is False
        assert booking.total_amount is None

    def test_reserved_free_bookings_count_as_used(self):
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))

        with pytest.raises(FreeBookingsExhaustedError):
            price_booking(booking, self.free_compensation, reserved=2)

    def test_excluded_booking_is_not_counted(self):
        used = self.use_free_bookings(2)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))

        price_booking(booking, self.free_compensation, exclude_booking=used[0])

        assert booking.uses_free_booking is True

    def test_string_start_date_is_accepted(self):
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))
        booking.start_date = "2027-03-01"

        price_booking(booking, self.free_compensation)

        assert booking.uses_free_booking is True


class TestNeedsQuotaReevaluation(FreeBookingsQuotaTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()
        self.booking = BookingFactory(
            title="existing",
            organization=self.organization,
            resource=self.resource,
            compensation=self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
        )

    def test_new_booking_is_reevaluated(self):
        assert needs_quota_reevaluation(
            None, self.organization, self.free_compensation, datetime.date(2027, 3, 1)
        )
        assert needs_quota_reevaluation(
            self.unsaved_booking(datetime.date(2027, 3, 1)),
            self.organization,
            self.free_compensation,
            datetime.date(2027, 3, 1),
        )

    def test_organization_change_is_reevaluated(self):
        assert needs_quota_reevaluation(
            self.booking,
            OrganizationFactory(),
            self.free_compensation,
            datetime.date(2027, 3, 1),
        )

    def test_compensation_change_is_reevaluated(self):
        assert needs_quota_reevaluation(
            self.booking,
            self.organization,
            self.paid_compensation,
            datetime.date(2027, 3, 1),
        )

    def test_year_change_is_reevaluated(self):
        assert needs_quota_reevaluation(
            self.booking,
            self.organization,
            self.free_compensation,
            datetime.date(2028, 3, 1),
        )
        assert needs_quota_reevaluation(
            self.booking, self.organization, self.free_compensation, "2028-03-01"
        )

    def test_other_changes_are_not_reevaluated(self):
        assert not needs_quota_reevaluation(
            self.booking,
            self.organization,
            self.free_compensation,
            datetime.date(2027, 11, 30),
        )


class TestGenerateBookingWithQuota(FreeBookingsQuotaTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()
        self.other_resource = ResourceFactory()
        self.free_compensation.resource.add(self.other_resource)

    def booking_data(self, start_date, hours=2, compensation=None, **kwargs):
        start = timezone.make_aware(
            datetime.datetime.combine(start_date, datetime.time(10))
        )
        end = start + datetime.timedelta(hours=hours)
        data = {
            "user": self.user.slug,
            "title": "Meeting",
            "resource": self.resource.slug,
            "organization": self.organization.slug,
            "timespan": [start.isoformat(), end.isoformat()],
            "start_date": start_date.isoformat(),
            "end_date": start_date.isoformat(),
            "start_time": start.time().isoformat(),
            "end_time": end.time().isoformat(),
            "compensation": (compensation or self.free_compensation).id,
            "invoice_address": {},
            "activity_description": "Meeting",
            "number_of_attendees": 5,
        }
        data.update(kwargs)
        return data

    def existing_booking(self, **kwargs):
        defaults = {
            "title": "existing",
            "organization": self.organization,
            "user": self.user,
            "resource": self.resource,
            "compensation": self.free_compensation,
            "start_date": datetime.date(2027, 3, 1),
            "start_time": datetime.time(10),
            "end_time": datetime.time(12),
            "status": BookingStatus.CONFIRMED,
        }
        defaults.update(kwargs)
        return BookingFactory(**defaults)

    def test_new_booking_uses_a_free_booking(self):
        booking = generate_booking(self.booking_data(datetime.date(2027, 3, 1)))

        assert booking.uses_free_booking is True
        assert booking.total_amount is None

    def test_new_booking_in_exhausted_year_raises(self):
        self.use_free_bookings(2)

        with pytest.raises(FreeBookingsExhaustedError):
            generate_booking(self.booking_data(datetime.date(2027, 3, 1)))

    def test_same_year_edit_with_longer_duration_and_other_room_stays_free(self):
        booking = self.existing_booking(uses_free_booking=True)
        self.use_free_bookings(1)
        data = self.booking_data(
            datetime.date(2027, 3, 1),
            hours=4,
            booking_id=booking.id,
            resource=self.other_resource.slug,
        )

        edited = generate_booking(data)

        assert edited.uses_free_booking is True
        assert edited.compensation == self.free_compensation
        assert edited.resource == self.other_resource
        assert edited.total_amount is None

    def test_title_edit_of_pre_quota_booking_is_accepted(self):
        booking = self.existing_booking(uses_free_booking=False)
        self.use_free_bookings(2)
        data = self.booking_data(
            datetime.date(2027, 3, 1), booking_id=booking.id, title="New title"
        )

        edited = generate_booking(data)

        assert edited.title == "New title"
        assert edited.uses_free_booking is False
        assert edited.compensation == self.free_compensation

    def test_edit_into_exhausted_year_is_rejected(self):
        booking = self.existing_booking(uses_free_booking=True)
        self.use_free_bookings(2, year=2028)
        data = self.booking_data(datetime.date(2028, 3, 1), booking_id=booking.id)

        with pytest.raises(FreeBookingsExhaustedError):
            generate_booking(data)

    def test_edit_into_other_year_uses_that_years_allowance(self):
        booking = self.existing_booking(uses_free_booking=True)
        data = self.booking_data(datetime.date(2028, 3, 1), booking_id=booking.id)

        edited = generate_booking(data)

        assert edited.uses_free_booking is True

    def test_paid_booking_switched_to_consuming_compensation(self):
        booking = self.existing_booking(
            compensation=self.paid_compensation, total_amount=30
        )
        self.use_free_bookings(1)
        data = self.booking_data(datetime.date(2027, 3, 1), booking_id=booking.id)

        edited = generate_booking(data)

        assert edited.uses_free_booking is True
        assert edited.total_amount is None
        assert edited.compensation == self.free_compensation

    def test_free_booking_switched_to_paid_compensation(self):
        booking = self.existing_booking(uses_free_booking=True)
        data = self.booking_data(
            datetime.date(2027, 3, 1),
            booking_id=booking.id,
            compensation=self.paid_compensation,
        )

        edited = generate_booking(data)

        assert edited.uses_free_booking is False
        assert edited.total_amount == 30  # noqa: PLR2004


class TestSaveBookingWithQuota(TestGenerateBookingWithQuota):
    def test_stored_values_match_the_priced_booking(self):
        booking = generate_booking(self.booking_data(datetime.date(2027, 3, 1)))

        saved = save_booking(self.user, booking)
        saved.refresh_from_db()

        assert saved.uses_free_booking is True
        assert saved.total_amount is None
        assert saved.compensation == self.free_compensation

    def test_booking_is_repriced_at_save(self):
        self.use_free_bookings(1)
        booking = generate_booking(self.booking_data(datetime.date(2027, 3, 1)))
        assert booking.uses_free_booking is True
        # another booking of the organization takes the last free booking
        self.use_free_bookings(1, year=2027)

        with pytest.raises(FreeBookingsExhaustedError):
            save_booking(self.user, booking)

        assert not Booking.objects.filter(title="Meeting").exists()

    def test_submitted_hidden_compensation_is_rejected(self):
        self.use_free_bookings(2)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))
        booking.compensation = self.free_compensation
        booking.uses_free_booking = True

        with pytest.raises(FreeBookingsExhaustedError):
            save_booking(self.user, booking)

    def test_pre_quota_edit_is_saved_unchanged(self):
        booking = self.existing_booking(uses_free_booking=False)
        self.use_free_bookings(2)
        data = self.booking_data(
            datetime.date(2027, 3, 1), booking_id=booking.id, title="New title"
        )

        saved = save_booking(self.user, generate_booking(data))
        saved.refresh_from_db()

        assert saved.title == "New title"
        assert saved.uses_free_booking is False


class TestIsBookableByOrganizationWithQuota(FreeBookingsQuotaTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()

    def test_consuming_compensation_rejected_when_exhausted(self):
        self.use_free_bookings(2)

        assert not is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
        )

    def test_consuming_compensation_accepted_while_free_bookings_remain(self):
        self.use_free_bookings(1)

        assert is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
        )

    def test_paid_compensation_is_not_affected(self):
        self.use_free_bookings(2)

        assert is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.paid_compensation,
            start_date=datetime.date(2027, 3, 1),
        )

    def test_without_start_date_the_quota_is_not_checked(self):
        self.use_free_bookings(2)

        assert is_bookable_by_organization(
            self.user, self.organization, self.resource, self.free_compensation
        )

    def test_manager_follows_the_same_rule(self):
        manager_user = UserFactory()
        ManagerFactory(user=manager_user)
        self.use_free_bookings(2)

        assert not is_bookable_by_organization(
            manager_user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
        )
        assert is_bookable_by_organization(
            manager_user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2028, 3, 1),
        )

    def test_pre_quota_edit_is_accepted(self):
        booking = BookingFactory(
            title="existing",
            organization=self.organization,
            resource=self.resource,
            compensation=self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
            uses_free_booking=False,
        )
        self.use_free_bookings(2)

        assert is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2027, 11, 1),
            booking=booking,
        )

    def test_edit_into_exhausted_year_is_rejected(self):
        booking = BookingFactory(
            title="existing",
            organization=self.organization,
            resource=self.resource,
            compensation=self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
            uses_free_booking=True,
        )
        self.use_free_bookings(2, year=2028)

        assert not is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2028, 3, 1),
            booking=booking,
        )

    def test_series_in_exhausted_year_accepted_with_paid_fallback_available(self):
        self.use_free_bookings(2)

        assert is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
            is_series=True,
        )

    def test_series_in_exhausted_year_rejected_without_paid_fallback(self):
        self.paid_compensation.is_active = False
        self.paid_compensation.save()
        self.use_free_bookings(2)

        assert not is_bookable_by_organization(
            self.user,
            self.organization,
            self.resource,
            self.free_compensation,
            start_date=datetime.date(2027, 3, 1),
            is_series=True,
        )


class FreeBookingsSeriesTestMixin(FreeBookingsQuotaTestMixin):
    """Series of the limited organization, priced against its free bookings."""

    series_counter = 0

    def set_up_quota(self):
        super().set_up_quota()
        patcher = patch_thread_pool()
        patcher.start()
        self.addCleanup(patcher.stop)

    def quota_series(self, rrule, *, with_fallback=True, **kwargs):
        FreeBookingsSeriesTestMixin.series_counter += 1
        defaults = {
            "title": f"series-{FreeBookingsSeriesTestMixin.series_counter}",
            "organization": self.organization,
            "resource": self.resource,
            "user": self.user,
            "compensation": self.free_compensation,
            "fallback_compensation": self.paid_compensation if with_fallback else None,
            "is_quota_priced": True,
            "total_amount_per_booking": None,
            "rrule": rrule,
            "start_time": datetime.time(10),
            "end_time": datetime.time(12),
            "status": BookingStatus.CONFIRMED,
        }
        defaults.update(kwargs)
        return BookingSeriesFactory(**defaults)

    def generate(self, booking_series):
        start = next(iter(rrulestr(booking_series.rrule)))
        end = datetime.datetime(2029, 1, 1, tzinfo=datetime.UTC)
        return generate_bookings(booking_series, start, end)

    def occurrence(self, booking_series, start_date, **kwargs):
        defaults = {
            "title": f"occurrence-{start_date.isoformat()}",
            "booking_series": booking_series,
            "organization": self.organization,
            "resource": self.resource,
            "user": self.user,
            "compensation": self.free_compensation,
            "status": BookingStatus.UNAVAILABLE,
            "start_date": start_date,
            "start_time": datetime.time(10),
            "end_time": datetime.time(12),
            "uses_free_booking": False,
            "total_amount": None,
        }
        defaults.update(kwargs)
        return BookingFactory(**defaults)


WEEKLY_2027 = "DTSTART:20270104T100000Z\nRRULE:FREQ=WEEKLY;COUNT=4"


class TestGenerateBookingsWithQuota(FreeBookingsSeriesTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()

    def test_first_occurrences_free_then_fallback(self):
        bookings = self.generate(self.quota_series(WEEKLY_2027))

        assert len(bookings) == 4  # noqa: PLR2004
        for booking in bookings[:2]:
            assert booking.uses_free_booking is True
            assert booking.compensation == self.free_compensation
            assert booking.total_amount is None
        for booking in bookings[2:]:
            assert booking.uses_free_booking is False
            assert booking.compensation == self.paid_compensation
            assert booking.total_amount == 30  # noqa: PLR2004

    def test_existing_free_bookings_count(self):
        self.use_free_bookings(1)

        bookings = self.generate(self.quota_series(WEEKLY_2027))

        assert [booking.uses_free_booking for booking in bookings] == [
            True,
            False,
            False,
            False,
        ]

    def test_allowance_resets_in_the_next_year(self):
        rrule = "DTSTART:20271220T100000Z\nRRULE:FREQ=WEEKLY;COUNT=4"

        bookings = self.generate(self.quota_series(rrule))

        assert [booking.start_date.year for booking in bookings] == [
            2027,
            2027,
            2028,
            2028,
        ]
        assert all(booking.uses_free_booking for booking in bookings)

    def test_unavailable_occurrence_does_not_use_a_free_booking(self):
        BookingFactory(
            title="blocker",
            resource=self.resource,
            status=BookingStatus.CONFIRMED,
            start_date=datetime.date(2027, 1, 11),
            start_time=datetime.time(10),
            end_time=datetime.time(12),
        )

        bookings = self.generate(self.quota_series(WEEKLY_2027))

        assert bookings[1].status == BookingStatus.UNAVAILABLE
        assert bookings[1].uses_free_booking is False
        assert [booking.uses_free_booking for booking in bookings] == [
            True,
            False,
            True,
            False,
        ]
        assert bookings[3].compensation == self.paid_compensation

    def test_unpriceable_occurrences_are_dropped(self):
        bookings = self.generate(self.quota_series(WEEKLY_2027, with_fallback=False))

        assert len(bookings) == 2  # noqa: PLR2004
        assert all(booking.uses_free_booking for booking in bookings)

    def test_series_crossing_the_valid_from_date(self):
        rrule = "DTSTART:20261102T100000Z\nRRULE:FREQ=WEEKLY;COUNT=12"

        bookings = self.generate(self.quota_series(rrule))

        in_2026 = [booking for booking in bookings if booking.start_date.year == 2026]  # noqa: PLR2004
        in_2027 = [booking for booking in bookings if booking.start_date.year == 2027]  # noqa: PLR2004
        assert len(in_2026) == 9  # noqa: PLR2004
        for booking in in_2026:
            assert booking.uses_free_booking is False
            assert booking.compensation == self.free_compensation
            assert booking.total_amount is None
        assert [booking.uses_free_booking for booking in in_2027] == [True, True, False]
        assert in_2027[2].compensation == self.paid_compensation

    def test_legacy_series_keeps_the_series_pricing(self):
        self.use_free_bookings(2)
        series = self.quota_series(WEEKLY_2027, is_quota_priced=False)

        bookings = self.generate(series)

        assert len(bookings) == 4  # noqa: PLR2004
        for booking in bookings:
            assert booking.compensation == self.free_compensation
            assert booking.uses_free_booking is False
            assert booking.total_amount is None


class TestExtendBookingSeriesWithQuota(FreeBookingsSeriesTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()
        today = timezone.now().date()
        self.target_date = today + timedelta(days=731)
        self.daily_rrule = f"DTSTART:{today:%Y%m%d}T100000Z\nRRULE:FREQ=DAILY"

    def test_occurrence_uses_a_free_booking_when_one_is_left(self):
        self.quota_series(self.daily_rrule)

        new_bookings = extend_booking_series()

        assert len(new_bookings) == 1
        assert new_bookings[0].start_date == self.target_date
        assert new_bookings[0].uses_free_booking is True

    def test_exhausted_year_uses_the_fallback_at_its_current_rate(self):
        self.use_free_bookings(2, year=self.target_date.year)
        self.quota_series(self.daily_rrule)
        self.paid_compensation.hourly_rate = 20
        self.paid_compensation.save()

        new_bookings = extend_booking_series()

        assert len(new_bookings) == 1
        assert new_bookings[0].compensation == self.paid_compensation
        assert new_bookings[0].total_amount == 40  # noqa: PLR2004
        assert new_bookings[0].uses_free_booking is False

    def test_dropped_without_fallback(self):
        self.use_free_bookings(2, year=self.target_date.year)
        series = self.quota_series(self.daily_rrule, with_fallback=False)

        new_bookings = extend_booking_series()

        assert new_bookings == []
        assert not Booking.objects.filter(booking_series=series).exists()

    def test_dropped_when_the_fallback_is_no_longer_usable(self):
        self.use_free_bookings(2, year=self.target_date.year)
        self.quota_series(self.daily_rrule)
        self.paid_compensation.is_active = False
        self.paid_compensation.save()

        assert extend_booking_series() == []

    def test_legacy_series_keeps_the_series_pricing(self):
        self.use_free_bookings(2, year=self.target_date.year)
        self.quota_series(self.daily_rrule, is_quota_priced=False)

        new_bookings = extend_booking_series()

        assert len(new_bookings) == 1
        assert new_bookings[0].compensation == self.free_compensation
        assert new_bookings[0].total_amount is None
        assert new_bookings[0].uses_free_booking is False

    def test_failure_in_one_series_keeps_the_others(self):
        failing = self.quota_series(self.daily_rrule)
        working = self.quota_series(self.daily_rrule, resource=ResourceFactory())
        self.free_compensation.resource.add(working.resource)
        self.paid_compensation.resource.add(working.resource)

        def explode_once(booking_series, start, end):
            if booking_series == failing:
                msg = "boom"
                raise RuntimeError(msg)
            return generate_bookings(booking_series, start, end)

        with patch(
            "re_sharing.bookings.services_booking_series.generate_bookings",
            side_effect=explode_once,
        ):
            new_bookings = extend_booking_series()

        assert [booking.booking_series for booking in new_bookings] == [working]


class TestSaveBookingSeriesWithQuota(FreeBookingsSeriesTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()

    def series_data(self, *, with_fallback=True, compensation=None):
        start = datetime.datetime(2027, 1, 4, 10, tzinfo=datetime.UTC)
        end = start + timedelta(hours=2)
        return {
            "user": self.user.slug,
            "title": "Weekly meeting",
            "resource": self.resource.slug,
            "organization": self.organization.slug,
            "timespan": [start.isoformat(), end.isoformat()],
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "compensation": (compensation or self.free_compensation).id,
            "fallback_compensation": self.paid_compensation.id
            if with_fallback
            else None,
            "rrule_string": WEEKLY_2027,
            "start": start,
            "invoice_address": "",
            "activity_description": "Meeting",
        }

    def test_saved_series_is_quota_priced_with_fallback(self):
        bookings, series, _bookable, pricing = create_booking_series_and_bookings(
            self.series_data()
        )

        bookings, series = save_booking_series(self.user, bookings, series)

        series.refresh_from_db()
        assert series.is_quota_priced is True
        assert series.fallback_compensation == self.paid_compensation
        assert pricing == {
            "free": 2,
            "paid": 2,
            "unavailable": 0,
            "dropped": 0,
            "rate": 15,
            "total": 60,
        }
        assert (
            Booking.objects.filter(
                booking_series=series, uses_free_booking=True
            ).count()
            == 2  # noqa: PLR2004
        )

    def test_rejected_when_the_compensation_is_not_bookable(self):
        restricted = CompensationFactory(
            hourly_rate=None,
            counts_against_free_bookings=True,
            resource=[self.resource],
        )
        restricted.organization_groups.add(OrganizationGroupFactory())
        bookings, series, _b, _p = create_booking_series_and_bookings(
            self.series_data(compensation=restricted)
        )

        with pytest.raises(PermissionDenied):
            save_booking_series(self.user, bookings, series)

        assert not BookingSeries.objects.exists()
        assert not Booking.objects.filter(title="Weekly meeting").exists()

    def test_rejected_with_an_unusable_fallback(self):
        bookings, series, _b, _p = create_booking_series_and_bookings(
            self.series_data()
        )
        self.paid_compensation.is_active = False
        self.paid_compensation.save()

        with pytest.raises(PermissionDenied):
            save_booking_series(self.user, bookings, series)

        assert not BookingSeries.objects.exists()

    def test_rejected_when_a_required_fallback_is_missing(self):
        bookings, series, _b, _p = create_booking_series_and_bookings(
            self.series_data(with_fallback=False)
        )

        with pytest.raises(PermissionDenied):
            save_booking_series(self.user, bookings, series)

        assert not BookingSeries.objects.exists()

    def test_occurrences_are_repriced_at_save(self):
        bookings, series, _b, pricing = create_booking_series_and_bookings(
            self.series_data()
        )
        assert pricing["free"] == 2  # noqa: PLR2004
        self.use_free_bookings(1)

        save_booking_series(self.user, bookings, series)

        saved = Booking.objects.filter(booking_series=series).order_by("start_date")
        assert [booking.uses_free_booking for booking in saved] == [
            True,
            False,
            False,
            False,
        ]
        assert saved[1].compensation == self.paid_compensation


class TestManagerConfirmBookingSeriesWithQuota(FreeBookingsSeriesTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()
        self.manager_user = UserFactory(is_staff=True)
        self.series = self.quota_series(WEEKLY_2027, status=BookingStatus.PENDING)

    def test_unavailable_occurrence_uses_a_free_booking_when_one_is_left(self):
        self.use_free_bookings(1)
        booking = self.occurrence(self.series, datetime.date(2027, 3, 1))

        manager_confirm_booking_series(self.manager_user, self.series.uuid)

        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.uses_free_booking is True
        assert booking.compensation == self.free_compensation

    def test_unavailable_occurrence_priced_with_fallback_when_none_is_left(self):
        self.use_free_bookings(2)
        booking = self.occurrence(self.series, datetime.date(2027, 3, 1))

        manager_confirm_booking_series(self.manager_user, self.series.uuid)

        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.uses_free_booking is False
        assert booking.compensation == self.paid_compensation
        assert booking.total_amount == 30  # noqa: PLR2004

    def test_unavailable_occurrence_deleted_when_it_cannot_be_priced(self):
        self.series.fallback_compensation = None
        self.series.save()
        self.use_free_bookings(2)
        booking = self.occurrence(self.series, datetime.date(2027, 3, 1))
        pending = self.occurrence(
            self.series, datetime.date(2027, 3, 8), status=BookingStatus.PENDING
        )

        manager_confirm_booking_series(self.manager_user, self.series.uuid)

        assert not Booking.objects.filter(pk=booking.pk).exists()
        pending.refresh_from_db()
        assert pending.status == BookingStatus.CONFIRMED

    def test_occurrences_are_handled_in_date_order(self):
        self.use_free_bookings(1)
        later = self.occurrence(self.series, datetime.date(2027, 3, 8))
        earlier = self.occurrence(self.series, datetime.date(2027, 3, 1))

        manager_confirm_booking_series(self.manager_user, self.series.uuid)

        earlier.refresh_from_db()
        later.refresh_from_db()
        assert earlier.uses_free_booking is True
        assert later.uses_free_booking is False
        assert later.compensation == self.paid_compensation

    def test_still_overlapping_occurrence_stays_unavailable(self):
        BookingFactory(
            title="blocker",
            resource=self.resource,
            status=BookingStatus.CONFIRMED,
            start_date=datetime.date(2027, 3, 1),
            start_time=datetime.time(10),
            end_time=datetime.time(12),
        )
        booking = self.occurrence(self.series, datetime.date(2027, 3, 1))

        manager_confirm_booking_series(self.manager_user, self.series.uuid)

        booking.refresh_from_db()
        assert booking.status == BookingStatus.UNAVAILABLE
        assert booking.uses_free_booking is False

    def test_legacy_series_keeps_todays_behaviour(self):
        self.series.is_quota_priced = False
        self.series.save()
        self.use_free_bookings(2)
        booking = self.occurrence(self.series, datetime.date(2027, 3, 1))

        manager_confirm_booking_series(self.manager_user, self.series.uuid)

        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED
        assert booking.uses_free_booking is False
        assert booking.compensation == self.free_compensation


class TestFreeBookingsRemainingAfter(FreeBookingsQuotaTestMixin, TestCase):
    def setUp(self):
        self.set_up_quota()

    def test_new_free_booking_reports_the_remaining_count(self):
        self.use_free_bookings(1)
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))
        price_booking(booking, self.free_compensation)

        assert get_free_bookings_remaining_after(booking) == 0

    def test_saved_free_booking_is_not_counted_twice(self):
        booking = self.use_free_bookings(1)[0]

        assert get_free_bookings_remaining_after(booking) == 1

    def test_paid_booking_has_no_remaining_count(self):
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))
        price_booking(booking, self.paid_compensation)

        assert get_free_bookings_remaining_after(booking) is None

    def test_unlimited_allowance_has_no_remaining_count(self):
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))
        booking.uses_free_booking = True
        self.organization.organization_groups.add(OrganizationGroupFactory())

        assert get_free_bookings_remaining_after(booking) is None

    def test_save_rejects_a_booking_the_guard_refuses(self):
        # the compensation is priced fine but belongs to another group
        restricted = CompensationFactory(
            hourly_rate=None,
            counts_against_free_bookings=True,
            resource=[self.resource],
        )
        restricted.organization_groups.add(OrganizationGroupFactory())
        booking = self.unsaved_booking(datetime.date(2027, 3, 1))
        price_booking(booking, restricted)

        with pytest.raises(PermissionDenied):
            save_booking(self.user, booking)

    def test_create_booking_data_carries_the_fallback(self):
        form = Mock()
        form.cleaned_data = {
            "title": "Weekly",
            "resource": self.resource,
            "timespan": (
                timezone.now() + timedelta(days=1),
                timezone.now() + timedelta(days=1, hours=2),
            ),
            "organization": self.organization,
            "startdate": datetime.date(2027, 1, 4),
            "enddate": datetime.date(2027, 1, 4),
            "starttime": datetime.time(10),
            "endtime": datetime.time(12),
            "compensation": self.free_compensation,
            "invoice_address": {},
            "activity_description": "Meeting",
            "number_of_attendees": 5,
            "fallback_compensation": self.paid_compensation,
            "rrule_repetitions": "NO_REPETITIONS",
        }

        booking_data, rrule = create_booking_data(self.user, form)

        assert booking_data["fallback_compensation"] == self.paid_compensation.id
        assert rrule is None
