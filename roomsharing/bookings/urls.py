from django.urls import path

from .views import BookingListView
from .views import MyBookingsListView
from .views import create_booking

app_name = "bookings"
urlpatterns = [
    path("all/", BookingListView.as_view(), name="bookings_list"),
    path("", MyBookingsListView.as_view(), name="my_bookings_list"),
    path("new/", create_booking, name="booking_create"),
]
