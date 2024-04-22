from datetime import datetime
from datetime import time
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import ListView

from roomsharing.bookings.models import Booking
from roomsharing.rooms.models import Room


def room_detail_view(request, slug):
    room = get_object_or_404(Room, slug=slug)
    bookings = Booking.objects.filter(room=room)

    return render(
        request,
        "rooms/room_detail.html",
        {"room": room, "bookings": bookings},
    )


class RoomListView(ListView):
    model = Room
    template_name = "rooms/room_list.html"
    context_object_name = "rooms"


def get_weekly_bookings(request, slug):
    bookings = Booking.objects.filter(room__slug=slug)

    # Calculate the start and end dates for the week
    today = timezone.now().date()
    start_of_week = timezone.make_aware(
        datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time()),
    )
    end_of_week = timezone.make_aware(
        datetime.combine(start_of_week + timedelta(days=6), datetime.max.time()),
    )
    start_of_day = timezone.make_aware(
        datetime.combine(today - timedelta(days=today.weekday()), time(hour=8)),
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
    bookings = bookings.filter(timespan__overlap=(start_of_week, end_of_week))

    # Check if a time slot is booked
    for booking in bookings:
        booking_start = max(booking.timespan.lower, start_of_week)
        booking_end = min(booking.timespan.upper, end_of_week)
        while booking_start < booking_end:
            if start_of_week <= booking_start < end_of_week:
                day_index = (booking_start - start_of_day).days
                slot_index = (booking_start - start_of_day).seconds // (30 * 60)
                if 0 <= slot_index < number_of_slots:
                    time_slots[slot_index]["booked"][day_index] = True
            booking_start += timedelta(minutes=30)

    return render(
        request,
        "rooms/partials/get_weekly_bookings.html",
        {
            "bookings": bookings,
            "weekdays": weekdays,
            "time_slots": time_slots,
        },
    )
