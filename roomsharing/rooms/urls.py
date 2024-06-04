from django.urls import path

from .views import get_room_list
from .views import get_weekly_bookings
from .views import list_rooms_view
from .views import show_room_view

app_name = "rooms"
urlpatterns = [
    path("", list_rooms_view, name="list-rooms"),
    path("room-list/", get_room_list, name="get-room-list"),
    path("<slug:slug>/", show_room_view, name="show-room"),
    path(
        "<slug:slug>/weekly-bookings/",
        get_weekly_bookings,
        name="get-weekly-bookings",
    ),
]
