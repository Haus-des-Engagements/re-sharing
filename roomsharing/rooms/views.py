from datetime import datetime
from datetime import time
from datetime import timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.rooms.forms import RoomsListFilter
from roomsharing.rooms.models import Room
from roomsharing.utils.models import BookingStatus


def show_room_view(request, slug):
    room = get_object_or_404(Room, slug=slug)
    bookings = Booking.objects.filter(room=room)

    return render(
        request,
        "rooms/show_room.html",
        {"room": room, "bookings": bookings},
    )


def list_rooms_view(request):
    form = RoomsListFilter(request.POST or None)
    rooms = Room.objects.all()

    rooms = rooms.prefetch_related("roomimages_of_room")

    return render(
        request,
        "rooms/list_rooms.html",
        {"rooms": rooms, "form": form},
    )


def filter_rooms_view(request):
    form = RoomsListFilter(request.POST or None)
    rooms = Room.objects.all()

    if form.is_valid():
        max_persons = form.cleaned_data.get("max_persons")
        if max_persons:
            rooms = rooms.filter(max_persons__gte=max_persons)

        name = form.cleaned_data.get("name")
        if name:
            rooms = rooms.filter(name__icontains=name)

        start_datetime = form.cleaned_data.get("start_datetime")
        duration = form.cleaned_data.get("duration")
        if start_datetime and duration:
            end_datetime = start_datetime + timedelta(minutes=duration)
            overlapping_bookings = Booking.objects.filter(
                timespan__overlap=(start_datetime, end_datetime),
            )
            booked_room_ids = overlapping_bookings.values_list("room_id", flat=True)

            rooms = rooms.exclude(id__in=booked_room_ids)

        rooms = rooms.prefetch_related("roomimages_of_room")
        return render(
            request,
            "rooms/partials/list_filter_rooms.html",
            {"rooms": rooms, "form": form},
        )

    return HttpResponse(
        f'<p class="error">Your form submission was unsuccessful. '
        f"Please would you correct the errors? The current errors: {form.errors}</p>",
    )


def get_weekly_bookings(request, slug):
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
    weekly_bookings = (
        Booking.objects.filter(room__slug=slug)
        .filter(status=BookingStatus.CONFIRMED)
        .filter(timespan__overlap=(start_of_week, end_of_week))
    )

    # Check if a time slot is booked
    current_tz = timezone.get_current_timezone()
    for booking in weekly_bookings:
        booking_start = max(
            booking.timespan.lower.astimezone(current_tz),
            start_of_week,
        )
        booking_end = min(booking.timespan.upper.astimezone(current_tz), end_of_week)
        while booking_start < booking_end:
            # Restart the time with start of each day
            start_of_day = booking_start.replace(hour=8, minute=0, second=0)
            if start_of_week <= booking_start < end_of_week:
                day_index = (booking_start - start_of_week).days
                slot_index = (booking_start - start_of_day).seconds // (30 * 60)
                if 0 <= slot_index < number_of_slots:
                    time_slots[slot_index]["booked"][day_index] = True
            booking_start += timedelta(minutes=30)

    return render(
        request,
        "rooms/partials/get_weekly_bookings.html",
        {
            "weekly_bookings": weekly_bookings,
            "weekdays": weekdays,
            "time_slots": time_slots,
        },
    )
