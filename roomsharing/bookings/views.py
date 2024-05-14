from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .forms import BookingForm
from .models import Booking


@method_decorator(permission_required("is_staff"), name="dispatch")
class BookingListView(LoginRequiredMixin, ListView):
    context_object_name = "bookings_list"

    model = Booking

    queryset = Booking.objects.all()

    ordering = ["timespan"]
    template_name = "bookings/bookings_list.html"


class MyBookingsListView(LoginRequiredMixin, ListView):
    context_object_name = "bookings_list"
    model = Booking

    def get_queryset(self):
        user_organizations = self.request.user.organizations.all()
        return Booking.objects.filter(
            organization__in=user_organizations,
        )

    ordering = ["timespan"]
    template_name = "bookings/bookings_list.html"


@login_required
def create_booking(request):
    if request.method == "GET":
        # Extract startdate and starttime from query parameters
        startdate = request.GET.get("startdate")
        starttime = request.GET.get("starttime")
        user = request.user
        # Set initial data for the form
        initial_data = {}
        if startdate:
            initial_data["startdate"] = startdate
        if starttime:
            initial_data["starttime"] = starttime

        form = BookingForm(user=user, initial=initial_data)
        return render(request, "bookings/booking_form.html", {"form": form})

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user)
        if form.is_valid():
            form.save(user=request.user)
            return redirect(reverse_lazy("bookings:bookings_list"))

    form = BookingForm(user=request.user)
    return render(request, "bookings/booking_form.html", {"form": form})
