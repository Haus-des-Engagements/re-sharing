from .models import BookingPermission
from .models import Organization


def user_has_bookingpermission(user, booking):
    return (
        BookingPermission.objects.filter(organization=booking.organization)
        .filter(user=user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .exists()
    )


def user_has_normal_bookingpermission(user, organization):
    return (
        BookingPermission.objects.filter(organization=organization)
        .filter(user=user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .exists()
    )


def organizations_with_bookingpermission(user):
    return (
        Organization.objects.filter(organization_of_bookingpermission__user=user)
        .filter(
            organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED
        )
        .distinct()
    )


def user_has_admin_bookingpermission(user, organization):
    return (
        BookingPermission.objects.filter(user=user)
        .filter(organization=organization)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .filter(role=BookingPermission.Role.ADMIN)
        .exists()
    )
