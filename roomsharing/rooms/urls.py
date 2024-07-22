from django.urls import path

from .views import get_weekly_bookings_view
from .views import list_rooms_view
from .views import show_room_view

app_name = "rooms"
urlpatterns = [
    path("", list_rooms_view, name="list-rooms"),
    path(
        "<slug:slug>/get-weekly-bookings/",
        get_weekly_bookings_view,
        name="get-weekly-bookings",
    ),
    path("<slug:slug>/", show_room_view, name="show-room"),
]
