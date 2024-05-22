from django.urls import path

from .views import BookingListView
from .views import MyBookingsListView
from .views import booking_detail_view
from .views import create_booking
from .views import recurrence_view

app_name = "bookings"
urlpatterns = [
    path("all/", BookingListView.as_view(), name="bookings_list"),
    path("", MyBookingsListView.as_view(), name="my_bookings_list"),
    path("new/", create_booking, name="booking_create"),
    path("<slug:slug>/", booking_detail_view, name="detail"),
    path("recurrence/", recurrence_view, name="recurrence"),
]
