from django.urls import resolve
from django.urls import reverse


def test_bookings_list():
    assert reverse("bookings:bookings_list") == "/bookings/all/"
    assert resolve("/bookings/all/").view_name == "bookings:bookings_list"


def test_my_bookings_list():
    assert reverse("bookings:my_bookings_list") == "/bookings/"
    assert resolve("/bookings/").view_name == "bookings:my_bookings_list"
