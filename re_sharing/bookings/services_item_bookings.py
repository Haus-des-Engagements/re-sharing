"""Services for lendable item bookings."""

from datetime import datetime
from datetime import time
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingGroup
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.providers.models import LendingTimeSlot
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceRestriction
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus


def get_lendable_items():
    """Get all lendable items."""
    return Resource.objects.filter(type=Resource.ResourceTypeChoices.LENDABLE_ITEM)


def get_available_quantity(resource, start_datetime, end_datetime):
    """
    Calculate available quantity for a resource in a given time range.

    Args:
        resource: The lendable item resource
        start_datetime: Start of the booking period
        end_datetime: End of the booking period

    Returns:
        Available quantity (int)
    """
    if resource.quantity_available is None:
        return 0

    overlapping_bookings = Booking.objects.filter(
        resource=resource,
        status=BookingStatus.CONFIRMED,
        timespan__overlap=(start_datetime, end_datetime),
    )
    booked_quantity = (
        overlapping_bookings.aggregate(total=Sum("quantity"))["total"] or 0
    )
    return resource.quantity_available - booked_quantity


def get_pickup_slots():
    """Get all active pickup time slots."""
    return LendingTimeSlot.objects.filter(
        slot_type=LendingTimeSlot.SlotType.PICKUP,
        is_active=True,
    )


def get_return_slots():
    """Get all active return time slots."""
    return LendingTimeSlot.objects.filter(
        slot_type=LendingTimeSlot.SlotType.RETURN,
        is_active=True,
    )


def get_pickup_days():
    """Get list of weekdays when pickup is available."""
    return list(get_pickup_slots().values_list("weekday", flat=True))


def get_return_days():
    """Get list of weekdays when return is available."""
    return list(get_return_slots().values_list("weekday", flat=True))


def get_pickup_slot_for_date(date):
    """Get the pickup time slot for a specific date, or None."""
    return get_pickup_slots().filter(weekday=date.weekday()).first()


def get_return_slot_for_date(date):
    """Get the return time slot for a specific date, or None."""
    return get_return_slots().filter(weekday=date.weekday()).first()


# Legacy compatibility functions for views/templates
def get_lending_days():
    """Get list of weekdays when pickup is available. (Legacy name)"""
    return get_pickup_days()


def get_lending_time_window():
    """
    Get a default pickup time window as (start_time, end_time).

    Note: This returns the first slot's times. For per-day times,
    use get_pickup_slot_for_date() instead.
    """
    slot = get_pickup_slots().first()
    if slot:
        return slot.start_time, slot.end_time
    return time(10, 0), time(12, 0)


def get_return_time_window():
    """
    Get a default return time window as (start_time, end_time).

    Note: This returns the first slot's times. For per-day times,
    use get_return_slot_for_date() instead.
    """
    slot = get_return_slots().first()
    if slot:
        return slot.start_time, slot.end_time
    return time(14, 0), time(16, 0)


def is_valid_pickup_date(date):
    """Check if a date is valid for pickup."""
    slot = get_pickup_slot_for_date(date)
    if slot is None:
        return False
    # Check resource restrictions
    return not is_date_restricted_for_items(date)


def is_valid_return_date(date):
    """Check if a date is valid for return."""
    slot = get_return_slot_for_date(date)
    if slot is None:
        return False
    # Check resource restrictions
    return not is_date_restricted_for_items(date)


def is_date_restricted_for_items(date):
    """
    Check if a date is restricted for lendable items.

    For items, we only check if the date falls on a restricted day,
    ignoring the time component.
    """
    lendable_items = get_lendable_items()
    restrictions = ResourceRestriction.objects.filter(
        resources__in=lendable_items,
        is_active=True,
    ).distinct()

    for restriction in restrictions:
        # Check date range
        if restriction.start_date and date < restriction.start_date:
            continue
        if restriction.end_date and date > restriction.end_date:
            continue

        # Check day of week
        days = [int(d.strip()) for d in restriction.days_of_week.split(",")]
        if date.weekday() in days:
            return True

    return False


def calculate_booking_days(pickup_date, return_date):
    """Calculate the number of calendar days for a booking."""
    return (return_date - pickup_date).days + 1


def calculate_item_total(daily_rate, quantity, num_days):
    """Calculate total amount for an item booking."""
    if daily_rate is None:
        return Decimal("0.00")
    return Decimal(daily_rate) * quantity * num_days


def get_booking_timespan(pickup_date, return_date):
    """
    Create the timespan for a booking based on pickup and return dates.

    Uses the specific day's pickup start time and return end time.
    """
    pickup_slot = get_pickup_slot_for_date(pickup_date)
    return_slot = get_return_slot_for_date(return_date)

    # Use slot times if available, otherwise fall back to defaults
    pickup_start = pickup_slot.start_time if pickup_slot else time(10, 0)
    return_end = return_slot.end_time if return_slot else time(16, 0)

    start_datetime = timezone.make_aware(datetime.combine(pickup_date, pickup_start))
    end_datetime = timezone.make_aware(datetime.combine(return_date, return_end))

    return (start_datetime, end_datetime)


def validate_item_booking_data(pickup_date, return_date, items, user, organization):
    """
    Validate item booking data before creating.

    Args:
        pickup_date: Date for pickup
        return_date: Date for return
        items: List of dicts with 'resource_id' and 'quantity'
        user: User making the booking
        organization: Organization for the booking

    Raises:
        ValidationError: If validation fails
    """
    errors = []

    # Validate dates
    if pickup_date >= return_date:
        errors.append(_("Return date must be after pickup date"))

    if not is_valid_pickup_date(pickup_date):
        pickup_days = get_pickup_days()
        day_names = [_get_weekday_name(d) for d in pickup_days]
        errors.append(
            _("Pickup only available on %(days)s") % {"days": ", ".join(day_names)}
        )

    if not is_valid_return_date(return_date):
        return_days = get_return_days()
        day_names = [_get_weekday_name(d) for d in return_days]
        errors.append(
            _("Return only available on %(days)s") % {"days": ", ".join(day_names)}
        )

    # Validate items
    if not items:
        errors.append(_("Please select at least one item"))

    start_datetime, end_datetime = get_booking_timespan(pickup_date, return_date)

    for item in items:
        resource = Resource.objects.get(pk=item["resource_id"])
        quantity = item["quantity"]

        if quantity <= 0:
            continue

        available = get_available_quantity(resource, start_datetime, end_datetime)
        if quantity > available:
            errors.append(
                _("Only %(n)s available for %(item)s")
                % {"n": available, "item": resource.name}
            )

        # Check if resource is bookable by organization
        if not resource.is_bookable_by_organization(organization):
            errors.append(
                _("%(item)s is not available for your organization")
                % {"item": resource.name}
            )

    if errors:
        raise ValidationError(errors)


def _get_weekday_name(weekday_num):
    """Get localized weekday name."""
    from django.utils.dates import WEEKDAYS

    return str(WEEKDAYS[weekday_num])


@transaction.atomic
def create_item_booking_group(
    user: User,
    organization: Organization,
    pickup_date,
    return_date,
    items: list[dict],
) -> BookingGroup:
    """
    Create a BookingGroup with individual Bookings for each item.

    Args:
        user: User making the booking
        organization: Organization for the booking
        pickup_date: Date for pickup
        return_date: Date for return
        items: List of dicts with 'resource_id', 'quantity',
               and optionally 'compensation_id'

    Returns:
        Created BookingGroup

    Raises:
        PermissionDenied: If user doesn't have permission
        ValidationError: If validation fails
    """
    # Check permission
    if not user_has_bookingpermission(user, organization):
        raise PermissionDenied(
            _("You don't have permission to book for this organization")
        )

    # Validate
    validate_item_booking_data(pickup_date, return_date, items, user, organization)

    # Calculate timespan
    start_datetime, end_datetime = get_booking_timespan(pickup_date, return_date)
    num_days = calculate_booking_days(pickup_date, return_date)

    # Create BookingGroup
    booking_group = BookingGroup.objects.create(
        organization=organization,
        user=user,
        status=BookingStatus.PENDING,
    )

    # Create individual bookings
    for item in items:
        if item["quantity"] <= 0:
            continue

        resource = Resource.objects.get(pk=item["resource_id"])

        # Get compensation (use first available if not specified)
        compensation = None
        if item.get("compensation_id"):
            from re_sharing.resources.models import Compensation

            compensation = Compensation.objects.get(pk=item["compensation_id"])
        else:
            # Use first available compensation with daily_rate
            compensations = resource.get_bookable_compensations(organization)
            compensation = compensations.filter(daily_rate__isnull=False).first()
            if not compensation:
                compensation = compensations.first()

        # Ensure we have a compensation
        if not compensation:
            raise ValidationError(
                _("No compensation available for %(item)s") % {"item": resource.name}
            )

        daily_rate = compensation.daily_rate if compensation else None
        total_amount = calculate_item_total(daily_rate, item["quantity"], num_days)

        # Re-verify availability with lock
        available = get_available_quantity(resource, start_datetime, end_datetime)
        if item["quantity"] > available:
            raise ValidationError(
                _("Some items are no longer available. Please adjust your selection.")
            )

        Booking.objects.create(
            title=resource.name,
            organization=organization,
            user=user,
            resource=resource,
            timespan=(start_datetime, end_datetime),
            status=BookingStatus.PENDING,
            booking_group=booking_group,
            quantity=item["quantity"],
            start_date=pickup_date,
            end_date=return_date,
            start_time=start_datetime.time(),
            end_time=end_datetime.time(),
            compensation=compensation,
            total_amount=total_amount,
            number_of_attendees=1,
            activity_description=_("Equipment loan"),
            is_item_booking=True,
        )

    return booking_group


def get_user_booking_groups(user: User):
    """Get all BookingGroups for a user."""
    return BookingGroup.objects.filter(user=user).prefetch_related(
        "bookings_of_bookinggroup",
        "bookings_of_bookinggroup__resource",
    )


def get_booking_group(user: User, slug: str) -> BookingGroup:
    """
    Get a BookingGroup by slug, checking permissions.

    Raises:
        PermissionDenied: If user doesn't have access
    """
    from django.shortcuts import get_object_or_404

    booking_group = get_object_or_404(BookingGroup, slug=slug)

    # Check if user has access
    if booking_group.user != user and not user.is_staff:
        # Check if user has permission for the organization
        if not user_has_bookingpermission(user, booking_group.organization):
            raise PermissionDenied

    return booking_group


def cancel_booking_group(user: User, slug: str) -> BookingGroup:
    """
    Cancel an entire BookingGroup.

    Raises:
        PermissionDenied: If user doesn't have access
        ValidationError: If not cancelable
    """
    booking_group = get_booking_group(user, slug)

    if not booking_group.is_cancelable():
        raise ValidationError(_("This booking cannot be cancelled"))

    booking_group.cancel_all_bookings()
    return booking_group


def cancel_item_in_booking_group(
    user: User, group_slug: str, booking_id: int
) -> Booking:
    """
    Cancel a single item booking within a BookingGroup.

    The BookingGroup status remains unchanged.

    Raises:
        PermissionDenied: If user doesn't have access
        ValidationError: If not cancelable
    """
    booking_group = get_booking_group(user, group_slug)

    booking = booking_group.bookings_of_bookinggroup.get(pk=booking_id)

    if not booking.is_cancelable():
        raise ValidationError(_("This item cannot be cancelled"))

    booking.status = BookingStatus.CANCELLED
    booking.save()

    return booking


# Manager functions


def manager_confirm_booking_group(user: User, slug: str) -> BookingGroup:
    """
    Confirm an entire BookingGroup (manager action).

    This confirms the group and all child bookings.
    """
    from django.shortcuts import get_object_or_404

    if not user.is_staff and not hasattr(user, "manager"):
        raise PermissionDenied

    booking_group = get_object_or_404(BookingGroup, slug=slug)
    booking_group.confirm_all_bookings()
    return booking_group


def manager_cancel_booking_group(user: User, slug: str) -> BookingGroup:
    """
    Cancel an entire BookingGroup (manager action).
    """
    from django.shortcuts import get_object_or_404

    if not user.is_staff and not hasattr(user, "manager"):
        raise PermissionDenied

    booking_group = get_object_or_404(BookingGroup, slug=slug)
    booking_group.cancel_all_bookings()
    return booking_group


def manager_cancel_item_in_booking_group(
    user: User, group_slug: str, booking_id: int
) -> Booking:
    """
    Cancel a single item booking within a BookingGroup (manager action).
    """
    from django.shortcuts import get_object_or_404

    if not user.is_staff and not hasattr(user, "manager"):
        raise PermissionDenied

    booking_group = get_object_or_404(BookingGroup, slug=group_slug)
    booking = booking_group.bookings_of_bookinggroup.get(pk=booking_id)

    booking.status = BookingStatus.CANCELLED
    booking.save()

    return booking


def mark_items_picked_up(user: User, group_slug: str) -> BookingGroup:
    """Mark all items in a BookingGroup as picked up."""
    from django.shortcuts import get_object_or_404

    if not user.is_staff and not hasattr(user, "manager"):
        raise PermissionDenied

    booking_group = get_object_or_404(BookingGroup, slug=group_slug)
    now = timezone.now()

    booking_group.bookings_of_bookinggroup.filter(
        status=BookingStatus.CONFIRMED
    ).update(actual_pickup_time=now)

    return booking_group


def mark_items_returned(user: User, group_slug: str) -> BookingGroup:
    """Mark all items in a BookingGroup as returned."""
    from django.shortcuts import get_object_or_404

    if not user.is_staff and not hasattr(user, "manager"):
        raise PermissionDenied

    booking_group = get_object_or_404(BookingGroup, slug=group_slug)
    now = timezone.now()

    booking_group.bookings_of_bookinggroup.filter(
        status=BookingStatus.CONFIRMED
    ).update(actual_return_time=now)

    return booking_group
