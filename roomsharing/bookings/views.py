from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView
from django.views.generic import ListView

from .forms import BookingForm
from .models import Booking


@method_decorator(permission_required("is_staff"), name="dispatch")
class BookingListView(LoginRequiredMixin, ListView):
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


class BookingCreateView(LoginRequiredMixin, CreateView):
    template_name = "bookings/booking_form.html"
    form_class = BookingForm
    success_url = reverse_lazy("bookings:bookings_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)
