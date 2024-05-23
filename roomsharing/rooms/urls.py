from django.urls import path

from .views import get_room_list
from .views import get_weekly_bookings
from .views import room_detail_view
from .views import room_list_view

app_name = "rooms"
urlpatterns = [
    path("", room_list_view, name="list"),
    path("room-list/", get_room_list, name="get-room-list"),
    path("<slug:slug>/", room_detail_view, name="detail"),
    path(
        "<slug:slug>/weekly-bookings/",
        get_weekly_bookings,
        name="get-weekly-bookings",
    ),
]
