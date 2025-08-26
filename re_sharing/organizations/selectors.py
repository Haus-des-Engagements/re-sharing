"""
Organization selectors - functions for fetching data from the database.

Following HackSoft Django styleguide:
- Selectors handle database reads only
- No business logic or database writes
- Pure data access layer
"""

from django.db.models import QuerySet

from re_sharing.users.models import User

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
