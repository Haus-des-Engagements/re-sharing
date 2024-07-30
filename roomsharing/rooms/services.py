from datetime import datetime
from datetime import time
from datetime import timedelta

from dateutil import parser
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import AccessCode
from roomsharing.rooms.models import Room
from roomsharing.utils.models import BookingStatus


def get_weekly_bookings(room_slug, date_string):
    room = get_object_or_404(Room, slug=room_slug)
    # Calculate the start and end dates for the week
    date = parser.parse(date_string).date() if date_string else timezone.now().date()
    start_of_week = timezone.make_aware(
        datetime.combine(date - timedelta(days=date.weekday()), datetime.min.time()),
    )
    end_of_week = timezone.make_aware(
        datetime.combine(start_of_week + timedelta(days=6), datetime.max.time()),
    )
    start_of_day = timezone.make_aware(
        datetime.combine(date - timedelta(days=date.weekday()), time(hour=8)),
    )
    # Calculate the time slots for each day
    number_of_slots = 32
    time_slots = [
        {"time": start_of_day + timedelta(minutes=30) * i, "booked": [False] * 7}
        for i in range(number_of_slots)
    ]
    weekdays = [
        start_of_week + timedelta(days=i) for i in range(7)
    ]  # Weekdays from Monday to Sunday
    # Filter bookings for the current week
    weekly_bookings = (
        Booking.objects.filter(room=room)
        .filter(status=BookingStatus.CONFIRMED)
        .filter(timespan__overlap=(start_of_week, end_of_week))
    )
    # Check if a time slot is booked
    current_tz = timezone.get_current_timezone()
    if weekly_bookings:
        for booking in weekly_bookings:
            booking_start = max(
                booking.timespan.lower.astimezone(current_tz),
                start_of_week,
            )
            booking_end = min(
                booking.timespan.upper.astimezone(current_tz), end_of_week
            )
            while booking_start < booking_end:
                # Restart the time with start of each day
                start_of_day = booking_start.replace(hour=8, minute=0, second=0)
                if start_of_week <= booking_start < end_of_week:
                    day_index = (booking_start - start_of_week).days
                    slot_index = (booking_start - start_of_day).seconds // (30 * 60)
                    if 0 <= slot_index < number_of_slots:
                        time_slots[slot_index]["booked"][day_index] = True
                booking_start += timedelta(minutes=30)
    return room, time_slots, weekdays


def filter_rooms(persons_count, start_datetime):
    rooms = Room.objects.all()

    if persons_count:
        rooms = rooms.filter(max_persons__gte=persons_count)
    if start_datetime:
        start_datetime = timezone.make_aware(parser.parse(start_datetime))
        end_datetime = start_datetime + timedelta(minutes=30)
        overlapping_bookings = Booking.objects.filter(
            timespan__overlap=(start_datetime, end_datetime),
        )
        booked_room_ids = overlapping_bookings.values_list("room_id", flat=True)
        rooms = rooms.exclude(id__in=booked_room_ids)
    return rooms.prefetch_related("roomimages_of_room")


def get_access_code(room_slug, organization_slug, timestamp):
    room = get_object_or_404(Room, slug=room_slug)
    organization = get_object_or_404(Organization, slug=organization_slug)

    access_code = (
        AccessCode.objects.filter(
            Q(access=room.access)
            & Q(validity_start__lte=timestamp)
            & Q(organization=organization)
        )
        .order_by("-validity_start")
        .first()
    )

    # when there is no organization specific AccessCode,
    # we try to get the general, unspecific one
    if not access_code:
        access_code = (
            AccessCode.objects.filter(
                Q(access=room.access)
                & Q(validity_start__lte=timestamp)
                & Q(organization=None)
            )
            .order_by("-validity_start")
            .first()
        )

    return access_code
