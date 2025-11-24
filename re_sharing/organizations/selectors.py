"""
Organization selectors - functions for fetching data from the database.

Following HackSoft Django styleguide:
- Selectors handle database reads only
- No business logic or database writes
- Pure data access layer
"""

from datetime import timedelta

from django.db.models import Count
from django.db.models import DecimalField
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus

from .models import BookingPermission
from .models import Organization


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


def get_filtered_organizations(
    include_groups: list[int] | None = None,
    exclude_groups: list[int] | None = None,
    min_bookings: int | None = None,
    months: int | None = None,
    max_amount: float | None = None,
) -> QuerySet[Organization]:
    """
    Filter confirmed organizations based on criteria.

    Args:
        include_groups: List of OrganizationGroup IDs to include
        exclude_groups: List of OrganizationGroup IDs to exclude
        min_bookings: Minimum number of bookings required
        months: Number of months to look back for bookings
        max_amount: Maximum total amount (organizations above this are excluded)

    Returns:
        QuerySet of filtered Organization objects
    """
    queryset = Organization.objects.filter(status=Organization.Status.CONFIRMED)

    # Apply group filters
    if include_groups:
        queryset = queryset.filter(organization_groups__id__in=include_groups)

    if exclude_groups:
        queryset = queryset.exclude(organization_groups__id__in=exclude_groups)

    # Annotate with booking statistics if months is provided
    if months is not None:
        start_date = timezone.now() - timedelta(days=months * 30)
        queryset = queryset.annotate(
            booking_count=Count(
                "booking_of_organization",
                filter=Q(
                    booking_of_organization__status=BookingStatus.CONFIRMED,
                    booking_of_organization__timespan__startswith__gte=start_date,
                ),
            ),
            total_amount=Coalesce(
                Sum(
                    "booking_of_organization__total_amount",
                    filter=Q(
                        booking_of_organization__status=BookingStatus.CONFIRMED,
                        booking_of_organization__timespan__startswith__gte=start_date,
                    ),
                ),
                0,
                output_field=DecimalField(),
            ),
        )

        # Apply booking count filter if specified
        if min_bookings is not None:
            queryset = queryset.filter(booking_count__gte=min_bookings)

        # Apply max amount filter if specified
        if max_amount is not None:
            queryset = queryset.filter(total_amount__lte=max_amount)

    return queryset.distinct()


def get_organization_booking_count(organization: Organization, months: int) -> int:
    """
    Get the number of confirmed bookings for an organization in the last X months.

    Args:
        organization: The Organization instance
        months: Number of months to look back

    Returns:
        Number of confirmed bookings
    """
    start_date = timezone.now() - timedelta(days=months * 30)
    return organization.bookings_of_organization.filter(
        status=BookingStatus.CONFIRMED,
        timespan__startswith__gte=start_date,
    ).count()
