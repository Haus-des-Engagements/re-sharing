from django.shortcuts import get_object_or_404
from django.shortcuts import render

from roomsharing.rooms.models import Compensation
from roomsharing.rooms.models import Room
from roomsharing.rooms.services import filter_rooms
from roomsharing.rooms.services import planner_table
from roomsharing.rooms.services import show_room


def list_rooms_view(request):
    persons_count = request.GET.get("persons_count")
    start_datetime = request.GET.get("start_datetime")
    rooms = filter_rooms(persons_count, start_datetime)
    context = {"rooms": rooms}
    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/list_filter_rooms.html", context)

    return render(request, "rooms/list_rooms.html", context)


def show_room_view(request, room_slug):
    date_string = request.GET.get("date")
    room, timeslots, weekdays, dates = show_room(room_slug, date_string)

    context = {
        "room": room,
        "weekdays": weekdays,
        "timeslots": timeslots,
        "dates": dates,
    }
    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/weekly_bookings_table.html", context)

    return render(request, "rooms/show_room.html", context)


def planner_view(request):
    date_string = request.GET.get("date")
    rooms, timeslots, dates = planner_table(date_string)
    context = {"rooms": rooms, "timeslots": timeslots, "dates": dates}

    if request.headers.get("HX-Request"):
        return render(request, "rooms/partials/planner_table.html", context)
    return render(request, "rooms/planner.html", context)


def get_compensations(request):
    room_id = request.POST.get("room")
    if not room_id:
        return render(
            request, "bookings/partials/compensations.html", {"compensations": []}
        )
    room = get_object_or_404(Room, id=room_id)
    compensations = Compensation.objects.filter(room=room)
    return render(
        request,
        "bookings/partials/compensations.html",
        {"compensations": compensations},
    )
