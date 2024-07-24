from django.shortcuts import get_object_or_404
from django.shortcuts import render

from roomsharing.bookings.models import Booking
from roomsharing.rooms.models import Room
from roomsharing.rooms.services import filter_rooms
from roomsharing.rooms.services import get_weekly_bookings


def show_room_view(request, slug):
    room = get_object_or_404(Room, slug=slug)
    bookings = Booking.objects.filter(room=room)

    return render(
        request,
        "rooms/show_room.html",
        {"room": room, "bookings": bookings},
    )


def list_rooms_view(request):
    max_persons = request.GET.get("max_persons")
    room_name = request.GET.get("name")
    rooms = filter_rooms(room_name, max_persons)

    context = {"rooms": rooms}
    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/list_filter_rooms.html", context)

    return render(request, "rooms/list_rooms.html", context)


def get_weekly_bookings_view(request, room_slug):
    date_string = request.GET.get("date")
    time_slots, weekdays = get_weekly_bookings(room_slug, date_string)

    return render(
        request,
        "rooms/partials/get_weekly_bookings.html",
        {
            "weekdays": weekdays,
            "time_slots": time_slots,
        },
    )
