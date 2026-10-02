from datetime import date
from datetime import time
from unittest.mock import patch

from django.test import TestCase

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services_quota_transition import apply_free_bookings_quota
from re_sharing.bookings.services_quota_transition import get_legacy_consuming_bookings
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.utils.models import BookingStatus


class QuotaTransitionTestMixin:
    """A limited organization (5 free bookings from 2026) with legacy bookings."""

    allowance = 5
    valid_from = date(2026, 1, 1)

    def set_up_transition(self):
        self.organization = OrganizationFactory(
            name="Limited Org", status=Organization.Status.CONFIRMED
        )
        self.organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=self.allowance,
                free_bookings_valid_from=self.valid_from,
            )
        )
        self.resource = ResourceFactory(name="Room with rates")
        self.quota_only_resource = ResourceFactory(name="Quota-only room")
        self.free_compensation = CompensationFactory(
            name="Free of charge",
            hourly_rate=None,
            counts_against_free_bookings=True,
            resource=[self.resource, self.quota_only_resource],
        )
        self.cheap_compensation = CompensationFactory(
            name="Cheap", hourly_rate=15, resource=[self.resource]
        )
        self.expensive_compensation = CompensationFactory(
            name="Expensive", hourly_rate=20, resource=[self.resource]
        )
        self.counter = 0

    def legacy_series(self, resource=None, **kwargs):
        self.counter += 1
        defaults = {
            "title": f"legacy-series-{self.counter}",
            "organization": self.organization,
            "resource": resource or self.resource,
            "compensation": self.free_compensation,
            "is_quota_priced": False,
            "total_amount_per_booking": None,
            "status": BookingStatus.CONFIRMED,
        }
        defaults.update(kwargs)
        return BookingSeriesFactory(**defaults)

    def booking(self, start_date, **kwargs):
        self.counter += 1
        defaults = {
            "title": f"legacy-{self.counter}",
            "organization": self.organization,
            "resource": self.resource,
            "compensation": self.free_compensation,
            "status": BookingStatus.CONFIRMED,
            "start_date": start_date,
            "start_time": time(10),
            "end_time": time(12),
            "uses_free_booking": False,
            "total_amount": None,
        }
        defaults.update(kwargs)
        return BookingFactory(**defaults)

    def flagged_bookings(self, year, count):
        return [
            self.booking(date(year, 1, 10 + i), uses_free_booking=True)
            for i in range(count)
        ]


class TestGetLegacyConsumingBookings(QuotaTransitionTestMixin, TestCase):
    def setUp(self):
        self.set_up_transition()

    def test_standalone_booking_and_legacy_occurrence_selected_in_date_order(self):
        series = self.legacy_series()
        occurrence = self.booking(date(2027, 3, 8), booking_series=series)
        standalone = self.booking(date(2027, 3, 1))

        assert get_legacy_consuming_bookings(self.organization) == [
            standalone,
            occurrence,
        ]

    def test_excluded_bookings(self):
        quota_series = self.legacy_series(is_quota_priced=True)
        self.booking(date(2027, 3, 1), booking_series=quota_series)
        self.booking(date(2027, 3, 2), uses_free_booking=True)
        self.booking(date(2027, 3, 3), invoice_number="INV-1")
        self.booking(date(2026, 9, 1))  # already happened
        self.booking(
            date(2027, 3, 4), compensation=self.cheap_compensation, total_amount=30
        )
        self.booking(date(2027, 3, 5), status=BookingStatus.UNAVAILABLE)
        self.booking(date(2027, 3, 6), status=BookingStatus.CANCELLED)
        self.booking(date(2027, 3, 7), organization=OrganizationFactory())

        assert get_legacy_consuming_bookings(self.organization) == []

    def test_booking_before_the_valid_from_date_is_excluded(self):
        self.organization.organization_groups.clear()
        self.organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=5, free_bookings_valid_from=date(2027, 1, 1)
            )
        )
        self.booking(date(2026, 12, 1))
        limited = self.booking(date(2027, 1, 4))

        assert get_legacy_consuming_bookings(self.organization) == [limited]


class TestApplyFreeBookingsQuota(QuotaTransitionTestMixin, TestCase):
    def setUp(self):
        self.set_up_transition()

    def test_earliest_bookings_keep_the_remaining_free_bookings(self):
        self.flagged_bookings(2027, 2)
        legacy = [self.booking(date(2027, 3, 1 + i)) for i in range(6)]

        report = apply_free_bookings_quota(self.organization)

        for booking in legacy:
            booking.refresh_from_db()
        assert [booking.uses_free_booking for booking in legacy] == [
            True,
            True,
            True,
            False,
            False,
            False,
        ]
        assert report.kept_free == legacy[:3]
        assert report.charged == legacy[3:]
        assert report.allowance_by_year == {2027: {"allowance": 5, "remaining": 3}}
        for booking in legacy[3:]:
            assert booking.compensation == self.cheap_compensation
            assert booking.total_amount == 30  # noqa: PLR2004
        assert report.charged_total == 90  # noqa: PLR2004

    def test_allowance_applies_per_year(self):
        self.flagged_bookings(2027, 5)
        in_2027 = self.booking(date(2027, 3, 1))
        in_2028 = [self.booking(date(2028, 3, 1 + i)) for i in range(4)]

        apply_free_bookings_quota(self.organization)

        in_2027.refresh_from_db()
        assert in_2027.uses_free_booking is False
        for booking in in_2028:
            booking.refresh_from_db()
            assert booking.uses_free_booking is True

    def test_occurrence_without_paid_compensation_is_deleted(self):
        self.flagged_bookings(2027, 5)
        series = self.legacy_series(resource=self.quota_only_resource)
        occurrence = self.booking(
            date(2027, 3, 1),
            resource=self.quota_only_resource,
            booking_series=series,
        )

        report = apply_free_bookings_quota(self.organization)

        assert not Booking.objects.filter(pk=occurrence.pk).exists()
        assert [removed.start_date for removed in report.deleted] == [date(2027, 3, 1)]

    def test_standalone_booking_without_paid_compensation_is_cancelled(self):
        self.flagged_bookings(2027, 5)
        booking = self.booking(date(2027, 3, 1), resource=self.quota_only_resource)

        with patch(
            "re_sharing.organizations.mails.send_booking_cancellation_email"
        ) as cancellation_email:
            report = apply_free_bookings_quota(self.organization)

        booking.refresh_from_db()
        assert booking.status == BookingStatus.CANCELLED
        assert report.cancelled == [booking]
        cancellation_email.enqueue.assert_not_called()

    def test_legacy_series_get_fallback_and_marker(self):
        with_rates = self.legacy_series()
        quota_only = self.legacy_series(resource=self.quota_only_resource)
        paid = self.legacy_series(compensation=self.cheap_compensation)
        self.booking(date(2027, 3, 1), booking_series=with_rates)

        report = apply_free_bookings_quota(self.organization)

        for series in (with_rates, quota_only, paid):
            series.refresh_from_db()
        assert with_rates.is_quota_priced is True
        assert with_rates.fallback_compensation == self.cheap_compensation
        assert quota_only.is_quota_priced is True
        assert quota_only.fallback_compensation is None
        assert paid.is_quota_priced is False
        assert set(report.updated_series) == {with_rates, quota_only}

    def test_second_run_changes_nothing(self):
        self.flagged_bookings(2027, 4)
        self.booking(date(2027, 3, 1))
        self.booking(date(2027, 3, 2))
        self.legacy_series()
        apply_free_bookings_quota(self.organization)

        report = apply_free_bookings_quota(self.organization)

        assert report.nothing_to_do is True
        assert Booking.objects.filter(uses_free_booking=True).count() == 5  # noqa: PLR2004

    def test_dry_run_reports_without_changing(self):
        self.flagged_bookings(2027, 4)
        kept = self.booking(date(2027, 3, 1))
        charged = self.booking(date(2027, 3, 2))
        series = self.legacy_series(resource=self.quota_only_resource)
        removed = self.booking(
            date(2027, 3, 3), resource=self.quota_only_resource, booking_series=series
        )

        report = apply_free_bookings_quota(self.organization, dry_run=True)

        assert report.dry_run is True
        assert report.kept_free == [kept]
        assert report.charged == [charged]
        assert len(report.deleted) == 1
        assert report.updated_series == [series]
        kept.refresh_from_db()
        charged.refresh_from_db()
        series.refresh_from_db()
        assert kept.uses_free_booking is False
        assert charged.compensation == self.free_compensation
        assert series.is_quota_priced is False
        assert Booking.objects.filter(pk=removed.pk).exists()
        assert BookingSeries.objects.get(pk=series.pk).fallback_compensation is None
