from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from re_sharing.organizations.tests.factories import OrganizationFactory


class TestSendBookingReminderEmailsCommand(TestCase):
    @patch(
        "re_sharing.organizations.management.commands.send_booking_reminder_emails.send_booking_reminder_emails"
    )
    def test_command_calls_send_booking_reminder_emails(self, mock_send):
        """Test that command calls send_booking_reminder_emails with default days"""
        mock_send.return_value = (["booking1", "booking2"], date(2025, 10, 6))
        out = StringIO()

        call_command("send_booking_reminder_emails", stdout=out)

        mock_send.assert_called_once_with(days=5)
        assert "Reminders send for 2" in out.getvalue()
        assert "bookings (on 2025-10-06)" in out.getvalue()

    @patch(
        "re_sharing.organizations.management.commands.send_booking_reminder_emails.send_booking_reminder_emails"
    )
    def test_command_with_custom_days(self, mock_send):
        """Test command with custom days parameter"""
        mock_send.return_value = (["booking1"], date(2025, 10, 8))
        out = StringIO()

        call_command("send_booking_reminder_emails", "--days=7", stdout=out)

        mock_send.assert_called_once_with(days=7)
        assert "Reminders send for 1" in out.getvalue()


class TestSendMonthlyBookingsOverviewCommand(TestCase):
    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_bookings_overview"
    )
    def test_command_calls_send_monthly_bookings_overview(self, mock_send):
        """Test command calls send_monthly_bookings_overview with defaults"""
        mock_send.return_value = {
            "next_month_start": date(2025, 11, 1),
            "organizations_processed": 5,
            "organizations_list": ["org1", "org2"],
        }
        out = StringIO()

        call_command("send_monthly_bookings_overview", stdout=out)

        mock_send.assert_called_once_with(months=1, organizations=None)
        assert "Reminders send for 2025-11-01" in out.getvalue()
        assert "5 organizations" in out.getvalue()

    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_bookings_overview"
    )
    def test_command_with_custom_months(self, mock_send):
        """Test command with custom months parameter"""
        mock_send.return_value = {
            "next_month_start": date(2025, 11, 1),
            "organizations_processed": 3,
            "organizations_list": ["org1"],
        }
        out = StringIO()

        call_command("send_monthly_bookings_overview", "--months=2", stdout=out)

        mock_send.assert_called_once_with(months=2, organizations=None)

    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_bookings_overview"
    )
    def test_command_with_specific_organizations(self, mock_send):
        """Test command with specific organization slugs"""
        # Create test organizations with unique slugs for this test
        org1 = OrganizationFactory(slug="cmd-test-org-a")
        org2 = OrganizationFactory(slug="cmd-test-org-b")

        mock_send.return_value = {
            "next_month_start": date(2025, 11, 1),
            "organizations_processed": 2,
            "organizations_list": [org1.slug, org2.slug],
        }
        out = StringIO()

        call_command(
            "send_monthly_bookings_overview",
            "--organizations",
            "cmd-test-org-a",
            "cmd-test-org-b",
            stdout=out,
        )

        # Check that send was called
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[1]["months"] == 1
        # Verify organizations parameter was passed (not None)
        orgs = call_args[1]["organizations"]
        assert orgs is not None
        # The queryset should have been filtered by slugs (look for SQL IN clause)
        query_str = str(orgs.query)
        assert '"slug" IN' in query_str
        assert "cmd-test-org-a" in query_str
        assert "cmd-test-org-b" in query_str

    @patch(
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_bookings_overview"
    )
    def test_command_with_missing_organization(self, mock_send):
        """Test command with organization slug that doesn't exist"""
        OrganizationFactory(slug="existing-org")

        mock_send.return_value = {
            "next_month_start": date(2025, 11, 1),
            "organizations_processed": 1,
            "organizations_list": ["existing-org"],
        }
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
        "re_sharing.organizations.management.commands.send_monthly_bookings_overview.send_monthly_bookings_overview"
    )
    def test_command_with_no_organizations_found(self, mock_send):
        """Test command when none of the specified organizations exist"""
        mock_send.return_value = {
            "next_month_start": date(2025, 11, 1),
            "organizations_processed": 0,
            "organizations_list": [],
        }
        out = StringIO()

        call_command(
            "send_monthly_bookings_overview",
            "--organizations",
            "nonexistent-org",
            stdout=out,
        )

        output = out.getvalue()
        assert "Warning: Organizations not found" in output
