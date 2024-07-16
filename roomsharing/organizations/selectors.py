from .models import BookingPermission
from .models import Organization


def user_has_booking_permission(user, booking):
    return (
        BookingPermission.objects.filter(organization=booking.organization)
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
