from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .models import Booking


@method_decorator(permission_required("is_staff"), name="dispatch")
class BookingsListView(LoginRequiredMixin, ListView):
    context_object_name = "bookings_list"

    model = Booking

    queryset = Booking.objects.all()

    ordering = ["id"]
    template_name = "bookings/bookings_list.html"


class MyBookingsListView(LoginRequiredMixin, ListView):
    context_object_name = "bookings_list"
    model = Booking

    def get_queryset(self):
        user_organizations = self.request.user.organizations.all()
        return Booking.objects.filter(
            booking_group__organization__in=user_organizations,
        )

    ordering = ["id"]
    template_name = "bookings/bookings_list.html"
