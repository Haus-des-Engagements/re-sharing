from dateutil.rrule import DAILY
from dateutil.rrule import FR
from dateutil.rrule import MO
from dateutil.rrule import MONTHLY
from dateutil.rrule import SA
from dateutil.rrule import SU
from dateutil.rrule import TH
from dateutil.rrule import TU
from dateutil.rrule import WE
from dateutil.rrule import WEEKLY
from dateutil.rrule import rrule
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .forms import BookingForm
from .forms import RecurrenceForm
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
        return Booking.objects.filter(organization__in=user_organizations)

    ordering = ["id"]
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

    return render(request, "bookings/booking_form.html", {"form": form})


def recurrence_view(request):
    if request.method == "POST":
        form = RecurrenceForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data.get("start_date")
            end_date = form.cleaned_data.get("end_date")
            frequency = form.cleaned_data.get("frequency")
            interval = form.cleaned_data.get("interval") or 1
            bysetpos = form.cleaned_data.get("bysetpos")
            byweekday = form.cleaned_data.get("byweekday") or None
            bymonthday = form.cleaned_data.get("bymonthday")

            freq_dict = {
                "MONTHLY": MONTHLY,
                "WEEKLY": WEEKLY,
                "DAILY": DAILY,
            }

            weekdays_dict = {
                "MO": MO,
                "TU": TU,
                "WE": WE,
                "TH": TH,
                "FR": FR,
                "SA": SA,
                "SU": SU,
            }

            if byweekday:
                byweekday = [weekdays_dict.get(day) for day in byweekday]

            occurrences = list(
                rrule(
                    freq_dict[frequency],
                    interval=interval,
                    bysetpos=bysetpos,
                    byweekday=byweekday,
                    bymonthday=bymonthday,
                    dtstart=start_date,
                    until=end_date,
                ),
            )
            return render(
                request,
                "bookings/recurrence.html",
                {"occurrences": occurrences},
            )
    else:  # HTTP GET
        form = RecurrenceForm()

    return render(request, "bookings/recurrence.html", {"form": form})
