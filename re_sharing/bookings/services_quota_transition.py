"""
One-time transition of bookings created before the free bookings quota.

Bookings and series that existed when the quota was configured are not
counted and keep their pricing (ADR 0023). After the announcement grace
period the remaining ones of limited organizations are brought under the
quota: the earliest bookings of a year keep the remaining free bookings,
the rest is charged with the cheapest paid compensation of the room or,
without one, removed. Legacy series get the fallback and the quota marker so
the nightly extension prices their later occurrences.
"""

from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services_pricing import FreeBookingsExhaustedError
from re_sharing.bookings.services_pricing import price_booking
from re_sharing.organizations.models import Organization
from re_sharing.organizations.selectors import get_free_bookings_allowance
from re_sharing.organizations.selectors import get_remaining_free_bookings
from re_sharing.resources.selectors import get_paid_fallback_compensations
from re_sharing.utils.models import BookingStatus


@dataclass
class RemovedBooking:
    """What is left of a deleted occurrence for the report."""

    start_date: object
    resource: str
    title: str


@dataclass
class TransitionReport:
    organization: Organization
    dry_run: bool = False
    allowance_by_year: dict = field(default_factory=dict)
    kept_free: list = field(default_factory=list)
    charged: list = field(default_factory=list)
    deleted: list = field(default_factory=list)
    cancelled: list = field(default_factory=list)
    updated_series: list = field(default_factory=list)

    @property
    def charged_total(self) -> Decimal:
        return sum(
            (Decimal(str(booking.total_amount)) for booking in self.charged),
            Decimal(0),
        )

    @property
    def nothing_to_do(self) -> bool:
        return not (
            self.kept_free
            or self.charged
            or self.deleted
            or self.cancelled
            or self.updated_series
        )


def get_legacy_consuming_bookings(organization: Organization) -> list[Booking]:
    """
    Future, not yet invoiced bookings of the organization that use a consuming
    compensation but were never priced against the quota: standalone bookings
    and occurrences of series created before the quota, on dates where the
    organization's allowance is limited. Ordered by start.
    """
    bookings = (
        Booking.objects.filter(
            organization=organization,
            status__in=(BookingStatus.PENDING, BookingStatus.CONFIRMED),
            uses_free_booking=False,
            invoice_number="",
            compensation__counts_against_free_bookings=True,
            timespan__startswith__gt=timezone.now(),
        )
        .filter(
            Q(booking_series__isnull=True) | Q(booking_series__is_quota_priced=False)
        )
        .select_related("resource", "compensation", "booking_series")
        .order_by("timespan")
    )
    return [
        booking
        for booking in bookings
        if get_free_bookings_allowance(organization, booking.start_date) is not None
    ]


def get_legacy_consuming_series(organization: Organization):
    """Series created before the quota whose compensation consumes free bookings."""
    return (
        BookingSeries.objects.filter(
            organization=organization,
            is_quota_priced=False,
            compensation__counts_against_free_bookings=True,
        )
        .select_related("resource")
        .order_by("created")
    )


def _cheapest_fallback(organization, resource, cache):
    if resource.pk not in cache:
        cache[resource.pk] = (
            get_paid_fallback_compensations(organization, resource)
            .order_by("hourly_rate")
            .first()
        )
    return cache[resource.pk]


def apply_free_bookings_quota(
    organization: Organization, *, dry_run: bool = False
) -> TransitionReport:
    """
    Bring the legacy bookings and series of one organization under the quota.

    Runs under the organization's row lock in its own transaction. In a dry
    run the same work is done and rolled back, so the report shows the real
    outcome.
    """
    report = TransitionReport(organization=organization, dry_run=dry_run)
    fallbacks = {}
    with transaction.atomic():
        Organization.objects.select_for_update().get(pk=organization.pk)

        for booking in get_legacy_consuming_bookings(organization):
            year = booking.start_date.year
            if year not in report.allowance_by_year:
                # first booking of the year: nothing of this year is saved yet
                report.allowance_by_year[year] = {
                    "allowance": get_free_bookings_allowance(
                        organization, booking.start_date
                    ),
                    "remaining": get_remaining_free_bookings(
                        organization, booking.start_date
                    ),
                }
            fallback = _cheapest_fallback(organization, booking.resource, fallbacks)
            try:
                # saved one by one, so the remaining count already includes
                # the bookings kept free earlier in this run
                price_booking(
                    booking, booking.compensation, fallback_compensation=fallback
                )
            except FreeBookingsExhaustedError:
                if booking.booking_series_id is not None:
                    report.deleted.append(
                        RemovedBooking(
                            booking.start_date, str(booking.resource), booking.title
                        )
                    )
                    booking.delete()
                else:
                    booking.status = BookingStatus.CANCELLED
                    booking.save()
                    report.cancelled.append(booking)
                continue
            booking.save()
            if booking.uses_free_booking:
                report.kept_free.append(booking)
            else:
                report.charged.append(booking)

        for series in get_legacy_consuming_series(organization):
            series.fallback_compensation = _cheapest_fallback(
                organization, series.resource, fallbacks
            )
            series.is_quota_priced = True
            series.save()
            report.updated_series.append(series)

        if dry_run:
            transaction.set_rollback(True)
    return report
