from django.shortcuts import render

from roomsharing.rooms.services import filter_rooms
from roomsharing.rooms.services import get_weekly_bookings


def show_room_view(request, room_slug):
    date_string = request.GET.get("date")
    room, time_slots, weekdays = get_weekly_bookings(room_slug, date_string)

    context = {
        "room": room,
        "weekdays": weekdays,
        "time_slots": time_slots,
    }
    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/get_weekly_bookings.html", context)

    return render(request, "rooms/show_room.html", context)


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


def list_rooms_view(request):
    persons_count = request.GET.get("persons_count")
    start_datetime = request.GET.get("start_datetime")
    rooms = filter_rooms(persons_count, start_datetime)
    context = {"rooms": rooms}
    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/list_filter_rooms.html", context)

    return render(request, "rooms/list_rooms.html", context)
