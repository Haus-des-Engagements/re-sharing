from django.urls import path

from .views import cancel_booking_view
from .views import cancel_rrule_bookings_view
from .views import create_booking_data_form_view
from .views import create_bookingmessage_view
from .views import list_bookings_view
from .views import list_recurrences_view
from .views import preview_and_save_booking_view
from .views import preview_and_save_recurrence_view
from .views import show_booking_view
from .views import show_recurrence_view

app_name = "bookings"
urlpatterns = [
    path("", list_bookings_view, name="list-bookings"),  # GET bookings list
    path(
        "recurrences/", list_recurrences_view, name="list-recurrences"
    ),  # GET recurrence list
    path(
        "create-booking/", create_booking_data_form_view, name="create-booking"
    ),  # GET & POST booking form data
    path(
        "preview-booking/", preview_and_save_booking_view, name="preview-booking"
    ),  # GET booking data & POST single booking
    path(
        "preview-recurrence/",
        preview_and_save_recurrence_view,
        name="preview-recurrence",
    ),  # GET recurrence & POST recurrence
    path(
        "<slug:booking>/", show_booking_view, name="show-booking"
    ),  # GET booking object
    path(
        "recurrences/<uuid:rrule>/", show_recurrence_view, name="show-recurrence"
    ),  # GET recurrence object
    path(
        "recurrences/<uuid:rrule>/cancel-rrule-bookings/",
        cancel_rrule_bookings_view,
        name="cancel-rrule-bookings",
    ),
    path(
        "<slug:slug>/cancel-booking/",
        cancel_booking_view,
        name="cancel-booking",
    ),  # PATCH booking object
    path(
        "<slug:slug>/create-bookingmessage/",
        create_bookingmessage_view,
        name="create-bookingmessage",
    ),  # POST bookingmessage object
]
