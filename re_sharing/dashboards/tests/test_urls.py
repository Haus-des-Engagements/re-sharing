from django.urls import resolve
from django.urls import reverse


def test_list_bookings():
    assert reverse("dashboards:users_bookings_and_permissions") == "/dashboard/"
    assert (
        resolve("/dashboard/").view_name == "dashboards:users_bookings_and_permissions"
    )
