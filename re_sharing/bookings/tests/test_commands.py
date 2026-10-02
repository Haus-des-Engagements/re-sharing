from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from re_sharing.bookings.services_quota_transition import apply_free_bookings_quota
from re_sharing.bookings.tests.test_services_quota_transition import (
    QuotaTransitionTestMixin,
)
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory


class TestExtendBookingSeriesCommand(TestCase):
    @patch(
        "re_sharing.bookings.management.commands.extend_booking_series.extend_booking_series"
    )
    def test_command_calls_extend_booking_series(self, mock_extend):
        """Test that command calls the extend_booking_series function"""
        mock_extend.return_value = ["booking1", "booking2"]
        out = StringIO()

        call_command("extend_booking_series", stdout=out)

        mock_extend.assert_called_once()
        assert "Created bookings: ['booking1', 'booking2']" in out.getvalue()

    @patch(
        "re_sharing.bookings.management.commands.extend_booking_series.extend_booking_series"
    )
    def test_command_with_no_bookings_created(self, mock_extend):
        """Test command output when no bookings are created"""
        mock_extend.return_value = []
        out = StringIO()

        call_command("extend_booking_series", stdout=out)

        mock_extend.assert_called_once()
        assert "Created bookings: []" in out.getvalue()


class TestApplyFreeBookingsQuotaCommand(QuotaTransitionTestMixin, TestCase):
    def setUp(self):
        self.set_up_transition()
        self.flagged_bookings(2027, 3)
        self.kept = self.booking(date(2027, 3, 1))
        self.kept_too = self.booking(date(2027, 3, 2))
        self.charged = self.booking(date(2027, 3, 3))
        self.series = self.legacy_series()

    def run_command(self, *args, **kwargs):
        out = StringIO()
        call_command("apply_free_bookings_quota", *args, stdout=out, **kwargs)
        return out.getvalue()

    def test_summary_per_organization_and_totals(self):
        output = self.run_command()

        assert (
            "Limited Org: 2 kept free, 1 charged (30.00 €), 0 deleted, "
            "0 cancelled, 1 series updated" in output
        )
        assert "2027: allowance 5, remaining before run 2" in output
        assert (
            "Total: 2 kept free, 1 charged, 0 deleted, 0 cancelled, 1 series updated"
            in output
        )
        assert "2027-03-01" not in output

    def test_verbosity_two_lists_every_booking(self):
        quota_only_series = self.legacy_series(resource=self.quota_only_resource)
        self.booking(
            date(2027, 3, 4),
            resource=self.quota_only_resource,
            booking_series=quota_only_series,
        )
        self.booking(date(2027, 3, 5), resource=self.quota_only_resource)

        output = self.run_command(verbosity=2)

        assert "2027-03-01 Room with rates: free" in output
        assert "2027-03-03 Room with rates: charged 30.00 € (Cheap)" in output
        assert "2027-03-04 Quota-only room: deleted" in output
        assert "2027-03-05 Quota-only room: cancelled" in output
        assert f"series '{self.series.title}': fallback Cheap" in output
        assert f"series '{quota_only_series.title}': fallback none" in output

    def test_nothing_to_do_for_untouched_organizations(self):
        other = OrganizationFactory(
            name="Quiet Org", status=Organization.Status.CONFIRMED
        )
        other.organization_groups.add(self.organization.organization_groups.get())

        output = self.run_command()

        assert "Quiet Org: nothing to do" in output

    def test_dry_run_changes_nothing(self):
        output = self.run_command("--dry-run")

        assert "DRY RUN: Limited Org: 2 kept free, 1 charged" in output
        assert "DRY RUN: Total:" in output
        self.kept.refresh_from_db()
        self.series.refresh_from_db()
        assert self.kept.uses_free_booking is False
        assert self.series.is_quota_priced is False

    def test_restricted_to_given_organizations(self):
        other = OrganizationFactory(
            name="Other Org", status=Organization.Status.CONFIRMED
        )
        other.organization_groups.add(self.organization.organization_groups.get())
        other_booking = self.booking(date(2027, 4, 1), organization=other)

        output = self.run_command("--organizations", other.slug)

        assert "Limited Org" not in output
        other_booking.refresh_from_db()
        self.kept.refresh_from_db()
        assert other_booking.uses_free_booking is True
        assert self.kept.uses_free_booking is False

    def test_unknown_slug_fails_before_any_change(self):
        with pytest.raises(CommandError, match="unknown-org"):
            self.run_command("--organizations", self.organization.slug, "unknown-org")

        self.kept.refresh_from_db()
        assert self.kept.uses_free_booking is False

    def test_failure_in_one_organization_keeps_the_others(self):
        failing = OrganizationFactory(
            name="Zz Failing Org", status=Organization.Status.CONFIRMED
        )
        failing.organization_groups.add(self.organization.organization_groups.get())
        real_apply = apply_free_bookings_quota

        def explode_for_failing(organization, **kwargs):
            if organization == failing:
                msg = "boom"
                raise RuntimeError(msg)
            return real_apply(organization, **kwargs)

        err = StringIO()
        with (
            patch(
                "re_sharing.bookings.management.commands.apply_free_bookings_quota"
                ".apply_free_bookings_quota",
                side_effect=explode_for_failing,
            ),
            pytest.raises(CommandError, match="1 organization"),
        ):
            call_command("apply_free_bookings_quota", stdout=StringIO(), stderr=err)

        assert "Zz Failing Org: failed (boom)" in err.getvalue()
        self.kept.refresh_from_db()
        assert self.kept.uses_free_booking is True
