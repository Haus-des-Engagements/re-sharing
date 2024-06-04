from django.urls import path

from .views import cancel_booking
from .views import create_booking
from .views import filter_bookings_view
from .views import list_bookings_view
from .views import recurrence_view
from .views import show_booking_view
from .views import write_bookingmessage

app_name = "bookings"
urlpatterns = [
    path("", list_bookings_view, name="list-bookings"),
    path(
        "filter-bookings/",
        filter_bookings_view,
        name="filter-bookings",
    ),
    path("create-booking/", create_booking, name="create-booking"),
    path("<slug:slug>/", show_booking_view, name="show-booking"),
    path(
        "<slug:slug>/cancel-booking/<from_page>/",
        cancel_booking,
        name="cancel-booking",
    ),
    path(
        "<slug:slug>/write-bookingmessage/",
        write_bookingmessage,
        name="write-bookingmessage",
    ),
    path("recurrence/", recurrence_view, name="recurrence"),
]

htmx_patterns = []
