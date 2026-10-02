from datetime import date

from django.db.models import QuerySet
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingGroup
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.selectors import get_free_bookings_allowance
from re_sharing.organizations.selectors import get_free_bookings_used
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus


def get_users_bookings_and_permissions(
    *, user: User
) -> tuple[QuerySet[Booking], QuerySet[BookingPermission], QuerySet[BookingGroup]]:
    booking_permissions = BookingPermission.objects.filter(user=user)
    organizations = organizations_with_confirmed_bookingpermission(user)
    bookings = (
        Booking.objects.filter(organization__in=organizations)
        .filter(timespan__endswith__gte=timezone.now())
        .filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
        .filter(is_item_booking=False)
        .order_by("timespan")[:5]
    )
    # Get equipment loans (BookingGroups)
    equipment_loans = (
        BookingGroup.objects.filter(organization__in=organizations)
        .filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
        .prefetch_related(
            "bookings_of_bookinggroup", "bookings_of_bookinggroup__resource"
        )
        .order_by("-created")[:5]
    )
    return bookings, booking_permissions, equipment_loans


def get_free_bookings_overview(*, user: User) -> dict[int, list[dict]]:
    """
    Used and available free bookings per organization of the user, for the
    current and the following calendar year. Keyed by organization id; years
    in which the organization's allowance is unlimited are left out, and so
    are organizations without any limited year.
    """
    current_year = timezone.now().year
    overview = {}
    for organization in organizations_with_confirmed_bookingpermission(user):
        years = []
        for year in (current_year, current_year + 1):
            # the allowance can only become limited as the year goes on
            allowance = get_free_bookings_allowance(organization, date(year, 12, 31))
            if allowance is None:
                continue
            years.append(
                {
                    "year": year,
                    "used": get_free_bookings_used(organization, year),
                    "allowance": allowance,
                }
            )
        if years:
            overview[organization.id] = years
    return overview
