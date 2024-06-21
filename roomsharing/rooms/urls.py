from django.urls import path

from .views import filter_rooms_view
from .views import get_weekly_bookings
from .views import list_rooms_view
from .views import show_room_view

app_name = "rooms"
urlpatterns = [
    path("", list_rooms_view, name="list-rooms"),
    path("filter-rooms/", filter_rooms_view, name="filter-rooms"),
    path(
        "<slug:slug>/get-weekly-bookings/",
        get_weekly_bookings,
        name="get-weekly-bookings",
    ),
    path("<slug:slug>/", show_room_view, name="show-room"),
]
