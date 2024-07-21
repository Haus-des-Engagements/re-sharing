from django.urls import path

from .views import cancel_booking_view
from .views import create_booking_view
from .views import create_bookingmessage_view
from .views import list_bookings_view
from .views import list_recurrences_view
from .views import preview_booking_view
from .views import show_booking_view
from .views import show_recurrence_view

app_name = "bookings"
urlpatterns = [
    path("", list_bookings_view, name="list-bookings"),
    path("recurrences/", list_recurrences_view, name="list-recurrences"),
    path("create-booking/", create_booking_view, name="create-booking"),
    path("preview-booking/", preview_booking_view, name="preview-booking"),
    path("<slug:booking>/", show_booking_view, name="show-booking"),
    path("recurrences/<uuid:rrule>", show_recurrence_view, name="show-recurrence"),
    path(
        "<slug:slug>/cancel-booking/",
        cancel_booking_view,
        name="cancel-booking",
    ),
    path(
        "<slug:slug>/create-bookingmessage/",
        create_bookingmessage_view,
        name="create-bookingmessage",
    ),
]

htmx_patterns = []
