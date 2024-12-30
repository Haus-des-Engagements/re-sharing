from django.urls import path

from .views import cancel_booking_series_booking_view
from .views import cancel_booking_view
from .views import cancel_bookings_of_booking_series_view
from .views import create_booking_data_form_view
from .views import create_bookingmessage_view
from .views import list_booking_series_view
from .views import list_bookings_view
from .views import manager_cancel_booking_view
from .views import manager_cancel_rrule_view
from .views import manager_confirm_booking_view
from .views import manager_confirm_rrule_view
from .views import manager_filter_invoice_bookings_list_view
from .views import manager_list_bookings_view
from .views import manager_list_rrules_view
from .views import preview_and_save_booking_series_view
from .views import preview_and_save_booking_view
from .views import show_booking_series_view
from .views import show_booking_view

app_name = "bookings"
urlpatterns = [
    path("", list_bookings_view, name="list-bookings"),  # GET bookings list
    path(
        "manage-bookings/",
        manager_list_bookings_view,
        name="manager-list-bookings",
    ),
    path(
        "manage-invoices/",
        manager_filter_invoice_bookings_list_view,
        name="manager-list-invoices",
    ),
    path(
        "manage-recurrences/",
        manager_list_rrules_view,
        name="manager-list-recurrences",
    ),
    path(
        "manage-bookings/<uuid:rrule_uuid>/cancel-recurrence/",
        manager_cancel_rrule_view,
        name="manager-cancel-recurrence",
    ),
    path(
        "manage-bookings/<uuid:rrule_uuid>/confirm-recurrence/",
        manager_confirm_rrule_view,
        name="manager-confirm-recurrence",
    ),
    path(
        "manage-bookings/<slug:booking_slug>/cancel-booking/",
        manager_cancel_booking_view,
        name="manager-cancel-booking",
    ),
    path(
        "manage-bookings/<slug:booking_slug>/confirm-booking/",
        manager_confirm_booking_view,
        name="manager-confirm-booking",
    ),
    path(
        "booking-series/", list_booking_series_view, name="list-booking-series"
    ),  # GET booking_series list
    path(
        "create-booking/", create_booking_data_form_view, name="create-booking"
    ),  # GET & POST booking form data
    path(
        "preview-booking/", preview_and_save_booking_view, name="preview-booking"
    ),  # GET booking data & POST single booking
    path(
        "preview-booking-series/",
        preview_and_save_booking_series_view,
        name="preview-booking-series",
    ),  # GET recurrence & POST recurrence
    path(
        "<slug:booking>/", show_booking_view, name="show-booking"
    ),  # GET booking object
    path(
        "booking-series/<slug:booking_series>/",
        show_booking_series_view,
        name="show-booking-series",
    ),  # GET recurrence object
    path(
        "booking-series/<uuid:booking_series>/cancel-booking-series-bookings/",
        cancel_bookings_of_booking_series_view,
        name="cancel-booking-series-bookings",
    ),
    path(
        "<slug:slug>/cancel-booking/",
        cancel_booking_view,
        name="cancel-booking",
    ),  # PATCH booking object
    path(
        "<slug:slug>/cancel-booking-series-booking/",
        cancel_booking_series_booking_view,
        name="cancel-booking-series-booking",
    ),  # PATCH booking object
    path(
        "<slug:slug>/create-bookingmessage/",
        create_bookingmessage_view,
        name="create-bookingmessage",
    ),  # POST bookingmessage object
]
