from django.urls import path

from .views import cancel_booking_series_booking_view
from .views import cancel_booking_view
from .views import cancel_bookings_of_booking_series_view
from .views import create_booking_data_form_view
from .views import create_bookingmessage_view
from .views import list_booking_series_view
from .views import list_bookings_view
from .views import list_bookings_webview
from .views import manager_cancel_booking_series_view
from .views import manager_cancel_booking_view
from .views import manager_confirm_booking_series_view
from .views import manager_confirm_booking_view
from .views import manager_filter_invoice_bookings_list_view
from .views import manager_list_booking_series_view
from .views import manager_list_bookings_view
from .views import preview_and_save_booking_series_view
from .views import preview_and_save_booking_view
from .views import show_booking_series_view
from .views import show_booking_view
from .views import update_booking_view
from .views_item_bookings import cancel_booking_group_view
from .views_item_bookings import cancel_item_in_group_view
from .views_item_bookings import confirm_item_booking_view
from .views_item_bookings import create_item_booking_view
from .views_item_bookings import manager_cancel_booking_group_view
from .views_item_bookings import manager_cancel_item_in_group_view
from .views_item_bookings import manager_confirm_booking_group_view
from .views_item_bookings import manager_item_bookings_view
from .views_item_bookings import manager_show_booking_group_view
from .views_item_bookings import preview_item_booking_view
from .views_item_bookings import show_booking_group_view

app_name = "bookings"
urlpatterns = [
    path("", list_bookings_view, name="list-bookings"),  # GET bookings list
    path(
        "webview/", list_bookings_webview, name="list-bookings-webview"
    ),  # GET bookings list
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
        "manage-booking-series/",
        manager_list_booking_series_view,
        name="manager-list-booking_series",
    ),
    path(
        "manage-bookings/<uuid:booking_series_uuid>/cancel-booking-series/",
        manager_cancel_booking_series_view,
        name="manager-cancel-booking-series",
    ),
    path(
        "manage-bookings/<uuid:booking_series_uuid>/confirm-booking-series/",
        manager_confirm_booking_series_view,
        name="manager-confirm-booking-series",
    ),
    # Item bookings (lendable items)
    path("items/", create_item_booking_view, name="create-item-booking"),
    path("items/preview/", preview_item_booking_view, name="preview-item-booking"),
    path("items/confirm/", confirm_item_booking_view, name="confirm-item-booking"),
    path(
        "items/<slug:slug>/",
        show_booking_group_view,
        name="show-booking-group",
    ),
    path(
        "items/<slug:slug>/cancel/",
        cancel_booking_group_view,
        name="cancel-booking-group",
    ),
    path(
        "items/<slug:slug>/cancel-item/<int:booking_id>/",
        cancel_item_in_group_view,
        name="cancel-item-in-group",
    ),
    # Manager item bookings
    path(
        "manager/items/",
        manager_item_bookings_view,
        name="manager-item-bookings",
    ),
    path(
        "manager/items/<slug:slug>/",
        manager_show_booking_group_view,
        name="manager-show-booking-group",
    ),
    path(
        "manager/items/<slug:slug>/confirm/",
        manager_confirm_booking_group_view,
        name="manager-confirm-booking-group",
    ),
    path(
        "manager/items/<slug:slug>/cancel/",
        manager_cancel_booking_group_view,
        name="manager-cancel-booking-group",
    ),
    path(
        "manager/items/<slug:slug>/cancel-item/<int:booking_id>/",
        manager_cancel_item_in_group_view,
        name="manager-cancel-item-in-group",
    ),
    path(
        "<slug:booking_slug>/edit/",
        update_booking_view,
        name="update-booking",
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
