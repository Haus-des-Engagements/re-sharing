from django.db.models import QuerySet
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from roomsharing.users.models import User
from roomsharing.utils.models import BookingStatus


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
