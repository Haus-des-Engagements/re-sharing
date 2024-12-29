from datetime import datetime
from datetime import time
from datetime import timedelta

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.organizations.models import Organization
from re_sharing.resources.models import AccessCode
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Room
from re_sharing.utils.models import BookingStatus


def show_room(room_slug, date_string):
    room = get_object_or_404(Room, slug=room_slug)
    # Calculate the start and end dates for the week
    shown_date = (
        parser.parse(date_string).date() if date_string else timezone.now().date()
    )
    start_of_week = timezone.make_aware(
        datetime.combine(
            shown_date - timedelta(days=shown_date.weekday()), datetime.min.time()
        ),
    )
    end_of_week = timezone.make_aware(
        datetime.combine(start_of_week + timedelta(days=6), datetime.max.time()),
    )
    start_of_day = timezone.make_aware(
        datetime.combine(
            shown_date - timedelta(days=shown_date.weekday()), time(hour=6)
        ),
    )
    # Calculate the time slots for each day
    number_of_slots = 36
    time_slots = [
        {"time": start_of_day + timedelta(minutes=30) * i, "booked": [False] * 7}
        for i in range(number_of_slots)
    ]

    weekdays = [start_of_week + timedelta(days=i) for i in range(7)]

    time_slots = []
    for i in range(number_of_slots):
        slot = {"time": start_of_day + timedelta(minutes=30) * i, "booked": [False] * 7}
        for j in range(7):
            slot["booked"][j] = (
                f"?starttime={slot['time'].strftime('%H:%M')}&endtime="
                f"{(slot['time'] + relativedelta(minutes=90)).strftime('%H:%M')}"
                f"&startdate={weekdays[j].strftime('%Y-%m-%d')}&room={room.slug}"
            )
        time_slots.append(slot)

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
                start_of_day = booking_start.replace(hour=6, minute=0, second=0)
                if start_of_week <= booking_start < end_of_week:
                    day_index = (booking_start - start_of_week).days
                    slot_index = (booking_start - start_of_day).seconds // (30 * 60)
                    if 0 <= slot_index < number_of_slots:
                        time_slots[slot_index]["booked"][day_index] = True
                booking_start += timedelta(minutes=30)
    dates = {
        "previous_week": shown_date - timedelta(days=7),
        "shown_date": shown_date,
        "next_week": shown_date + timedelta(days=7),
    }
    compensations = Compensation.objects.filter(room=room)
    return room, time_slots, weekdays, dates, compensations


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


def planner_table(date_string):
    rooms = Room.objects.all().order_by("id")

    shown_date = (
        parser.parse(date_string).date() if date_string else timezone.now().date()
    )
    start_of_day = timezone.make_aware(
        datetime.combine(shown_date, time(hour=0)),
    )
    end_of_day = timezone.make_aware(
        datetime.combine(shown_date, time(hour=23, minute=59)),
    )

    # Calculate the time slots for each day
    number_of_slots = 48
    timeslots = [
        {
            "timeslot": i,
            "time": start_of_day + timedelta(minutes=30) * i,
            "slot": [
                {"booked": False, "booking_link": None} for _ in range(rooms.count())
            ],
        }
        for i in range(number_of_slots)
    ]
    daily_bookings = (
        Booking.objects.filter(room__in=rooms)
        .filter(status=BookingStatus.CONFIRMED)
        .filter(timespan__overlap=(start_of_day, end_of_day))
    )

    room_ids = [room.id for room in rooms]

    for booking in daily_bookings:
        booking_start = max(booking.timespan.lower, start_of_day)
        booking_end = min(booking.timespan.upper, end_of_day)

        # Convert booking start and end times to time slot indices
        start_index = int((booking_start - start_of_day).total_seconds() // 1800)
        end_index = int((booking_end - start_of_day).total_seconds() // 1800)

        room_index = room_ids.index(booking.room.id)

        # Mark corresponding time slots as booked
        for i in range(start_index, end_index):
            timeslots[i]["slot"][room_index]["booked"] = True

    for timeslot in timeslots:
        for i, room in enumerate(timeslot["slot"]):
            if not room["booked"]:
                room["booking_link"] = (
                    f"?starttime={timeslot['time'].strftime('%H:%M')}"
                    f"&endtime="
                    f"{(timeslot['time']+ relativedelta(minutes=90)).strftime('%H:%M')}"
                    f"&startdate={shown_date.strftime('%Y-%m-%d')}&room={rooms[i].slug}"
                )

    previous_day = shown_date - timedelta(days=1)
    next_day = shown_date + timedelta(days=1)
    dates = {
        "previous_day": previous_day,
        "shown_date": shown_date,
        "next_day": next_day,
    }
    return rooms, timeslots, dates
