from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView

from .models import Booking


class BookingsListView(LoginRequiredMixin, ListView):
    context_object_name = "bookings_list"
    login_url = reverse_lazy("account_login")
    model = Booking

    queryset = Booking.objects.all()

    ordering = ["id"]
    template_name = "bookings/bookings_list.html"
