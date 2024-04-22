from django.urls import path

from .views import RoomListView
from .views import get_weekly_bookings
from .views import room_detail_view

app_name = "rooms"
urlpatterns = [
    path("", RoomListView.as_view(), name="list"),
    path("<slug:slug>/", room_detail_view, name="detail"),
    path(
        "<slug:slug>/weekly-bookings/",
        get_weekly_bookings,
        name="get-weekly-bookings",
    ),
]
