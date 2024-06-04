from django.urls import resolve
from django.urls import reverse


def test_bookings_list():
    assert reverse("bookings:list-bookings") == "/bookings/"
    assert resolve("/bookings/").view_name == "bookings:list-bookings"
