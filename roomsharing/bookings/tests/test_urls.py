from django.urls import resolve
from django.urls import reverse

from roomsharing.bookings.models import Booking


def test_list_bookings():
    assert reverse("bookings:list-bookings") == "/bookings/"
    assert resolve("/bookings/").view_name == "bookings:list-bookings"


def test_show_booking(booking: Booking):
    assert (
        reverse("bookings:show-booking", kwargs={"booking": booking.slug})
        == f"/bookings/{booking.slug}/"
    )
    assert resolve(f"/bookings/{booking.slug}/").view_name == "bookings:show-booking"


def test_create_booking():
    assert reverse("bookings:create-booking") == "/bookings/create-booking/"
    assert resolve("/bookings/create-booking/").view_name == "bookings:create-booking"


def test_cancel_booking(booking: Booking):
    assert (
        reverse(
            "bookings:cancel-booking",
            kwargs={"slug": booking.slug},
        )
        == f"/bookings/{booking.slug}/cancel-booking/"
    )


def test_cancel_occurrence(booking: Booking):
    assert (
        reverse(
            "bookings:cancel-occurrence",
            kwargs={"slug": booking.slug},
        )
        == f"/bookings/{booking.slug}/cancel-occurrence/"
    )


def test_write_bookingmessage(booking: Booking):
    assert (
        reverse("bookings:create-bookingmessage", kwargs={"slug": booking.slug})
        == f"/bookings/{booking.slug}/create-bookingmessage/"
    )


def test_manager_list_bookings_view():
    assert reverse("bookings:manager-list-bookings") == "/bookings/manage-bookings/"
    assert (
        resolve("/bookings/manage-bookings/").view_name
        == "bookings:manager-list-bookings"
    )


def test_manager_cancel_booking(booking: Booking):
    assert (
        reverse(
            "bookings:manager-cancel-booking",
            kwargs={"booking_slug": booking.slug},
        )
        == f"/bookings/manage-bookings/{booking.slug}/cancel-booking/"
    )


def test_manager_confirm_booking(booking: Booking):
    assert (
        reverse(
            "bookings:manager-confirm-booking",
            kwargs={"booking_slug": booking.slug},
        )
        == f"/bookings/manage-bookings/{booking.slug}/confirm-booking/"
    )
