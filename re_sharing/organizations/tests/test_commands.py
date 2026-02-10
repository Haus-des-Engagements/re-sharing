from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from psycopg.types.range import Range

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.utils.models import BookingStatus


class TestSendBookingReminderEmailsCommand(TestCase):
    @patch(
        "re_sharing.organizations.management.commands.send_booking_reminder_emails.send_booking_reminder_email"
    )
    def test_command_enqueues_tasks_for_bookings(self, mock_task):
        """Test that command enqueues tasks for each eligible booking"""
        resource = ResourceFactory()
        organization = OrganizationFactory(monthly_bulk_access_codes=False)
        # Booking 5 days from now (default)
        dt_in_5_days = timezone.now() + timedelta(days=5)
        dt_in_5_days = dt_in_5_days.replace(hour=10, minute=0, second=0, microsecond=0)
        booking = BookingFactory(
            resource=resource,
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(dt_in_5_days, dt_in_5_days + timedelta(hours=2)),
        )
        out = StringIO()

        call_command("send_booking_reminder_emails", stdout=out)

        mock_task.enqueue.assert_called_once_with(booking.id)
        assert "Enqueued 1 reminder email tasks" in out.getvalue()

    @patch(
        "re_sharing.organizations.management.commands.send_booking_reminder_emails.send_booking_reminder_email"
    )
    def test_command_with_custom_days(self, mock_task):
        """Test command with custom days parameter"""
        resource = ResourceFactory()
        organization = OrganizationFactory(monthly_bulk_access_codes=False)
        # Booking 7 days from now
        dt_in_7_days = timezone.now() + timedelta(days=7)
        dt_in_7_days = dt_in_7_days.replace(hour=10, minute=0, second=0, microsecond=0)
        BookingFactory(
            resource=resource,
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(dt_in_7_days, dt_in_7_days + timedelta(hours=2)),
        )
        out = StringIO()

        call_command("send_booking_reminder_emails", "--days=7", stdout=out)

        mock_task.enqueue.assert_called_once()

    @patch(
        "re_sharing.organizations.management.commands.send_booking_reminder_emails.send_booking_reminder_email"
    )
    def test_command_excludes_bulk_access_code_organizations(self, mock_task):
        """Test that bookings from organizations with bulk codes are excluded"""
        resource = ResourceFactory()
        organization = OrganizationFactory(monthly_bulk_access_codes=True)
        dt_in_5_days = timezone.now() + timedelta(days=5)
        dt_in_5_days = dt_in_5_days.replace(hour=10, minute=0, second=0, microsecond=0)
        BookingFactory(
            resource=resource,
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(dt_in_5_days, dt_in_5_days + timedelta(hours=2)),
        )
        out = StringIO()

        call_command("send_booking_reminder_emails", stdout=out)

        mock_task.enqueue.assert_not_called()
        assert "Enqueued 0 reminder email tasks" in out.getvalue()


class TestSendMonthlyBookingsOverviewCommand(TestCase):
    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_overview_email"
    )
    def test_command_enqueues_tasks_for_organizations(self, mock_task):
        """Test command enqueues tasks for organizations with bookings"""
        resource = ResourceFactory()
        organization = OrganizationFactory(monthly_bulk_access_codes=True)
        # Booking next month
        next_month = timezone.now() + timedelta(days=35)
        next_month = next_month.replace(
            day=10, hour=10, minute=0, second=0, microsecond=0
        )
        booking = BookingFactory(
            resource=resource,
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(next_month, next_month + timedelta(hours=2)),
        )
        out = StringIO()

        call_command("send_monthly_bookings_overview", stdout=out)

        mock_task.enqueue.assert_called_once()
        call_args = mock_task.enqueue.call_args
        assert call_args[0][0] == organization.id
        assert call_args[0][1] == [booking.id]
        assert "Enqueued 1 monthly overview email tasks" in out.getvalue()

    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_overview_email"
    )
    def test_command_with_custom_months(self, mock_task):
        """Test command with custom months parameter"""
        resource = ResourceFactory()
        organization = OrganizationFactory(monthly_bulk_access_codes=True)
        # Booking 2 months from now
        two_months = timezone.now() + timedelta(days=65)
        two_months = two_months.replace(
            day=10, hour=10, minute=0, second=0, microsecond=0
        )
        BookingFactory(
            resource=resource,
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(two_months, two_months + timedelta(hours=2)),
        )
        out = StringIO()

        call_command("send_monthly_bookings_overview", "--months=2", stdout=out)

        mock_task.enqueue.assert_called_once()

    def test_command_with_missing_organization_shows_warning(self):
        """Test command with organization slug that doesn't exist"""
        OrganizationFactory(slug="existing-org")
        out = StringIO()

        call_command(
            "send_monthly_bookings_overview",
            "--organizations",
            "existing-org",
            "missing-org",
            stdout=out,
        )

        output = out.getvalue()
        assert "Warning: Organizations not found:" in output
        assert "missing-org" in output

    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_overview_email"
    )
    def test_command_filters_by_specific_organizations(self, mock_task):
        """Test command with specific organization slugs filters correctly"""
        resource1 = ResourceFactory()
        resource2 = ResourceFactory()
        org1 = OrganizationFactory(name="Test Org One", monthly_bulk_access_codes=True)
        org2 = OrganizationFactory(name="Test Org Two", monthly_bulk_access_codes=True)
        next_month = timezone.now() + timedelta(days=35)
        next_month = next_month.replace(
            day=10, hour=10, minute=0, second=0, microsecond=0
        )
        BookingFactory(
            resource=resource1,
            organization=org1,
            status=BookingStatus.CONFIRMED,
            timespan=Range(next_month, next_month + timedelta(hours=2)),
        )
        BookingFactory(
            resource=resource2,
            organization=org2,
            status=BookingStatus.CONFIRMED,
            timespan=Range(next_month, next_month + timedelta(hours=2)),
        )
        out = StringIO()

        # Only request org1 using its actual slug
        call_command(
            "send_monthly_bookings_overview",
            "--organizations",
            org1.slug,
            stdout=out,
        )

        # Should only enqueue for org1
        mock_task.enqueue.assert_called_once()
        call_args = mock_task.enqueue.call_args
        assert call_args[0][0] == org1.id
