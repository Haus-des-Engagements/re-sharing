from django.urls import resolve
from django.urls import reverse

from roomsharing.bookings.models import Booking


def test_list_bookings():
    assert reverse("bookings:list-bookings") == "/bookings/"
    assert resolve("/bookings/").view_name == "bookings:list-bookings"


def test_show_booking(booking: Booking):
    assert (
        reverse("bookings:show-booking", kwargs={"slug": booking.slug})
        == f"/bookings/{booking.slug}/"
    )
    assert resolve(f"/bookings/{booking.slug}/").view_name == "bookings:show-booking"


def test_filter_bookings():
    assert reverse("bookings:filter-bookings") == "/bookings/filter-bookings/"
    assert resolve("/bookings/filter-bookings/").view_name == "bookings:filter-bookings"


def test_create_booking():
    assert reverse("bookings:create-booking") == "/bookings/create-booking/"
    assert resolve("/bookings/create-booking/").view_name == "bookings:create-booking"


def test_cancel_booking(booking: Booking):
    expected_url_details = f"/bookings/{booking.slug}/cancel-booking/detail/"
    assert (
        reverse(
            "bookings:cancel-booking",
            kwargs={"slug": booking.slug, "from_page": "detail"},
        )
        == expected_url_details
    )
    expected_url_list = f"/bookings/{booking.slug}/cancel-booking/list/"
    assert (
        reverse(
            "bookings:cancel-booking",
            kwargs={"slug": booking.slug, "from_page": "list"},
        )
        == expected_url_list
    )


def test_write_bookingmessage(booking: Booking):
    assert (
        reverse("bookings:write-bookingmessage", kwargs={"slug": booking.slug})
        == f"/bookings/{booking.slug}/write-bookingmessage/"
    )
