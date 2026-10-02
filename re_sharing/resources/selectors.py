"""
Resource selectors - functions for fetching data from the database.

Following HackSoft Django styleguide:
- Selectors handle database reads only
- No business logic or database writes
"""

from datetime import date

from django.db.models import Q
from django.db.models import QuerySet

from re_sharing.organizations.models import Organization
from re_sharing.organizations.selectors import get_remaining_free_bookings

from .models import Compensation
from .models import Resource


def get_compensations_for(
    organization: Organization, resource: Resource
) -> QuerySet[Compensation]:
    """Active compensations the organization may book for the resource."""
    org_groups = organization.organization_groups.all()
    return (
        Compensation.objects.filter(is_active=True)
        .filter(Q(resource=resource) | Q(resource=None))
        .filter(Q(organization_groups__in=org_groups) | Q(organization_groups=None))
        .distinct()
    )


def get_paid_fallback_compensations(
    organization: Organization, resource: Resource
) -> QuerySet[Compensation]:
    """
    Compensations with an hourly rate the organization may book for the
    resource. These are the candidates for the fallback of a booking series
    once the free bookings of a year are used up.
    """
    return get_compensations_for(organization, resource).filter(
        hourly_rate__isnull=False
    )


def get_bookable_compensations(
    organization: Organization,
    resource: Resource,
    on_date: date,
    booking=None,
    *,
    is_series: bool = False,
) -> tuple[QuerySet[Compensation], int | None]:
    """
    Compensations to offer for a booking of the organization on the resource
    starting on ``on_date``, and the remaining free bookings of that year
    (``None`` when unlimited).

    A compensation that counts against free bookings is left out once no free
    booking of the year is left, unless a series with a paid fallback is
    requested. While an existing booking is edited within its organization and
    year, its current compensation stays offered and the booking itself is not
    counted, so edits that are not re-priced remain possible.
    """
    compensations = get_compensations_for(organization, resource)
    keeps_current = (
        booking is not None
        and booking.organization_id == organization.pk
        and booking.start_date.year == on_date.year
    )
    remaining = get_remaining_free_bookings(
        organization, on_date, exclude_booking=booking if keeps_current else None
    )
    if remaining is None or remaining >= 1:
        return compensations, remaining
    if is_series and get_paid_fallback_compensations(organization, resource).exists():
        return compensations, remaining

    exhausted = Q(counts_against_free_bookings=True)
    if keeps_current:
        exhausted &= ~Q(pk=booking.compensation_id)
    return compensations.exclude(exhausted), remaining
