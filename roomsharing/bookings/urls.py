from django.urls import path

from .views import BookingCreateView
from .views import BookingListView
from .views import MyBookingsListView

app_name = "bookings"
urlpatterns = [
    path("all/", BookingListView.as_view(), name="bookings_list"),
    path("", MyBookingsListView.as_view(), name="my_bookings_list"),
    path("new/", BookingCreateView.as_view(), name="booking_create"),
]
