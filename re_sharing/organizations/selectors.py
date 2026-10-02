"""
Organization selectors - functions for fetching data from the database.

Following HackSoft Django styleguide:
- Selectors handle database reads only
- No business logic or database writes
- Pure data access layer
"""

from datetime import date
from datetime import datetime
from datetime import time

from django.db.models import Count
from django.db.models import DecimalField
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from re_sharing.resources.models import Resource
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus

from .models import BookingPermission
from .models import Organization
from .models import OrganizationGroup


def get_booking_permission(
    organization: Organization, user_slug: str
) -> BookingPermission | None:
    """Get booking permission for user in organization"""
    return BookingPermission.objects.filter(
        organization=organization, user__slug=user_slug
    ).first()


def get_user_permissions_for_organization(
    user: User, organization: Organization
) -> QuerySet[BookingPermission]:
    """Get all permissions for user in organization"""
    return BookingPermission.objects.filter(user=user, organization=organization)


def user_has_admin_permission(user: User, organization: Organization) -> bool:
    """Check if user has admin permission for organization"""
    if user.is_staff:
        return True

    if user.is_manager():
        manager = user.manager
        if manager.can_manage_organization(organization=organization):
            return True

    return BookingPermission.objects.filter(
        user=user,
        organization=organization,
        status=BookingPermission.Status.CONFIRMED,
        role=BookingPermission.Role.ADMIN,
    ).exists()


def get_user_by_email(email: str) -> User | None:
    """Get user by email address"""
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return None


CUSTOM_EMAIL_RESOURCE_TYPES = (
    Resource.ResourceTypeChoices.ROOM,
    Resource.ResourceTypeChoices.PARKING_LOT,
)


def get_custom_email_filterable_resources() -> QuerySet[Resource]:
    """Rooms and parking lots that can be used as a filter for custom emails."""
    return Resource.objects.filter(type__in=CUSTOM_EMAIL_RESOURCE_TYPES).order_by(
        "type", "name"
    )


def _confirmed_booking_filter(
    from_date: date | None = None,
    to_date: date | None = None,
    resource_ids: list[int] | None = None,
    prefix: str = "",
) -> Q:
    """
    Build the Q object selecting the bookings that count for custom email
    statistics: confirmed bookings whose start lies within the inclusive day
    range [from_date, to_date] (project time zone) on the given resources.

    An omitted bound is open. Empty resource_ids means all resources. Resource
    IDs that are not rooms or parking lots are ignored.

    Args:
        prefix: Lookup prefix when filtering through a relation
            (e.g. "booking_of_organization__").
    """
    booking_filter = Q(**{f"{prefix}status": BookingStatus.CONFIRMED})

    if from_date is not None:
        start = timezone.make_aware(datetime.combine(from_date, time.min))
        booking_filter &= Q(**{f"{prefix}timespan__startswith__gte": start})

    if to_date is not None:
        end = timezone.make_aware(datetime.combine(to_date, time.max))
        booking_filter &= Q(**{f"{prefix}timespan__startswith__lte": end})

    if resource_ids:
        resources = Resource.objects.filter(
            id__in=resource_ids, type__in=CUSTOM_EMAIL_RESOURCE_TYPES
        )
        booking_filter &= Q(**{f"{prefix}resource__in": resources})

    return booking_filter


def get_filtered_organizations(  # noqa: PLR0913
    include_groups: list[int] | None = None,
    exclude_groups: list[int] | None = None,
    min_bookings: int | None = None,
    max_amount: float | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    resource_ids: list[int] | None = None,
) -> QuerySet[Organization]:
    """
    Filter confirmed organizations based on criteria.

    Every organization is annotated with ``booking_count`` and ``total_amount``
    over its confirmed bookings starting within [from_date, to_date] on the
    selected resources (see ``_confirmed_booking_filter``).

    Args:
        include_groups: List of OrganizationGroup IDs to include
        exclude_groups: List of OrganizationGroup IDs to exclude
        min_bookings: Minimum number of counted bookings required
        max_amount: Maximum counted total amount (organizations above are excluded)
        from_date: First day of the counted period (inclusive), open if None
        to_date: Last day of the counted period (inclusive), open if None
        resource_ids: Only count bookings on these rooms/parking lots

    Returns:
        QuerySet of filtered Organization objects
    """
    queryset = Organization.objects.filter(status=Organization.Status.CONFIRMED)

    if include_groups:
        queryset = queryset.filter(organization_groups__id__in=include_groups)

    if exclude_groups:
        queryset = queryset.exclude(organization_groups__id__in=exclude_groups)

    booking_filter = _confirmed_booking_filter(
        from_date, to_date, resource_ids, prefix="booking_of_organization__"
    )
    queryset = queryset.annotate(
        booking_count=Count("booking_of_organization", filter=booking_filter),
        total_amount=Coalesce(
            Sum("booking_of_organization__total_amount", filter=booking_filter),
            0,
            output_field=DecimalField(),
        ),
    )

    if min_bookings is not None:
        queryset = queryset.filter(booking_count__gte=min_bookings)

    if max_amount is not None:
        queryset = queryset.filter(total_amount__lte=max_amount)

    return queryset.distinct()


def get_organization_booking_stats(
    organization: Organization,
    from_date: date | None = None,
    to_date: date | None = None,
    resource_ids: list[int] | None = None,
) -> dict:
    """
    Booking statistics for one organization using the same rules as
    ``get_filtered_organizations``.

    Returns:
        dict with ``booking_count`` (int) and ``total_amount`` (Decimal, 0 if none)
    """
    return organization.bookings_of_organization.filter(
        _confirmed_booking_filter(from_date, to_date, resource_ids)
    ).aggregate(
        booking_count=Count("id"),
        total_amount=Coalesce(Sum("total_amount"), 0, output_field=DecimalField()),
    )


FREE_BOOKINGS_COUNTED_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


def get_free_bookings_allowance(
    organization: Organization, on_date: date
) -> int | None:
    """
    Free bookings per calendar year the organization is entitled to for a
    booking starting on ``on_date``.

    The most generous allowance of all its groups wins. A group without a
    number, or whose valid-from date lies after ``on_date``, grants an
    unlimited allowance, which is represented by ``None``.
    """
    limited_allowances = []
    for group in organization.organization_groups.all():
        if group.free_bookings_per_year is None:
            return None
        if group.free_bookings_valid_from > on_date:
            return None
        limited_allowances.append(group.free_bookings_per_year)

    if not limited_allowances:
        return None
    return max(limited_allowances)


def is_free_bookings_allowance_limited_until(
    organization: Organization, last_date: date
) -> bool:
    """
    Whether the organization's allowance is limited on any date up to and
    including ``last_date``.

    A group's allowance can only change from unlimited to limited as the date
    moves forward, so checking ``last_date`` itself is sufficient.
    """
    return get_free_bookings_allowance(organization, last_date) is not None


def get_free_bookings_used(
    organization: Organization, year: int, exclude_booking=None
) -> int:
    """
    Number of the organization's pending or confirmed bookings starting in
    ``year`` that used a free booking. Every booking counts as one.
    """
    bookings = organization.bookings_of_organization.filter(
        uses_free_booking=True,
        start_date__year=year,
        status__in=FREE_BOOKINGS_COUNTED_STATUSES,
    )
    if exclude_booking is not None and exclude_booking.pk is not None:
        bookings = bookings.exclude(pk=exclude_booking.pk)
    return bookings.count()


def get_remaining_free_bookings(
    organization: Organization, on_date: date, exclude_booking=None
) -> int | None:
    """
    Free bookings left for a booking starting on ``on_date``: the allowance
    minus the used free bookings of that calendar year, never below zero.
    ``None`` when the allowance is unlimited.
    """
    allowance = get_free_bookings_allowance(organization, on_date)
    if allowance is None:
        return None
    used = get_free_bookings_used(organization, on_date.year, exclude_booking)
    return max(allowance - used, 0)


def get_limited_organizations() -> QuerySet[Organization]:
    """
    Confirmed organizations whose free bookings are limited: in a group that
    carries a number and in no group without one, because an unlimited group
    makes the whole organization unlimited.
    """
    limited_groups = OrganizationGroup.objects.filter(
        free_bookings_per_year__isnull=False
    )
    unlimited_groups = OrganizationGroup.objects.filter(
        free_bookings_per_year__isnull=True
    )
    return (
        Organization.objects.filter(
            status=Organization.Status.CONFIRMED,
            organization_groups__in=limited_groups,
        )
        .exclude(organization_groups__in=unlimited_groups)
        .distinct()
        .order_by("name")
    )
