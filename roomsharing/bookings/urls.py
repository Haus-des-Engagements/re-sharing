from django.urls import path

from .views import BookingsListView

app_name = "bookings"
urlpatterns = [
    path("all/", BookingsListView.as_view(), name="bookings_list"),
]
