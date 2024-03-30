from django.urls import path

from .views import bookings_list_view

app_name = "bookings"
urlpatterns = [
    path("all/", bookings_list_view, name="bookings_list"),
]
