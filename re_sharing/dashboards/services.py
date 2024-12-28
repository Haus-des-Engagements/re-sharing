from django.db.models import QuerySet
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus


def get_users_bookings_and_permissions(
    *, user: User
) -> tuple[QuerySet[Booking], QuerySet[BookingPermission]]:
    booking_permissions = BookingPermission.objects.filter(user=user)
    organizations = organizations_with_confirmed_bookingpermission(user)
    bookings = (
        Booking.objects.filter(organization__in=organizations)
        .filter(timespan__endswith__gte=timezone.now())
        .filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
        .order_by("timespan")[:5]
    )
    return bookings, booking_permissions
