from django.urls import path

from .views import booking_detail_view
from .views import booking_list_view
from .views import create_booking
from .views import get_filtered_booking_list
from .views import recurrence_view
from .views import write_booking_message

app_name = "bookings"
urlpatterns = [
    path("", booking_list_view, name="list"),
    path(
        "filtered-booking-list/",
        get_filtered_booking_list,
        name="filtered_booking_list",
    ),
    path("new/", create_booking, name="booking_create"),
    path(
        "<slug:slug>/write-booking-message",
        write_booking_message,
        name="write_booking_message",
    ),
    path("<slug:slug>/", booking_detail_view, name="detail"),
    path("recurrence/", recurrence_view, name="recurrence"),
]
