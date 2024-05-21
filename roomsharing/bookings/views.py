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
from django.shortcuts import get_object_or_404
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


def booking_detail_view(request, slug):
    booking = get_object_or_404(Booking, slug=slug)

    return render(
        request,
        "bookings/booking_details.html",
        {"booking": booking},
    )


@login_required
def create_booking(request):
    if request.method == "GET":
        # Extract startdate and starttime from query parameters
        startdate = request.GET.get("startdate")
        starttime = request.GET.get("starttime")
        enddate = request.GET.get("enddate")
        endtime = request.GET.get("endtime")
        user = request.user
        # Set initial data for the form
        initial_data = {}
        if startdate:
            initial_data["startdate"] = startdate
        if starttime:
            initial_data["starttime"] = starttime
        if enddate:
            initial_data["enddate"] = enddate
        if endtime:
            initial_data["endtime"] = endtime

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
            frequency = form.cleaned_data.get("frequency")
            interval = form.cleaned_data.get("interval") or 1
            bysetpos = (
                int(form.cleaned_data.get("bysetpos"))
                if form.cleaned_data.get("bysetpos")
                else None
            )
            byweekday = form.cleaned_data.get("byweekday") or None
            bymonthday = form.cleaned_data.get("bymonthday")
            bymonthday = int(bymonthday) if bymonthday else None
            recurrence_choice = form.cleaned_data.get("recurrence_choice")

            count = (
                form.cleaned_data.get("count") if recurrence_choice == "count" else None
            )
            end_date = (
                form.cleaned_data.get("end_date")
                if recurrence_choice == "end_date"
                else None
            )

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

            if freq_dict[frequency] == DAILY:
                bysetpos = None
                bymonthday = None
                byweekday = None
            elif freq_dict[frequency] == WEEKLY:
                bysetpos = None
                bymonthday = None

            occurrences = list(
                rrule(
                    freq_dict[frequency],
                    interval=interval,
                    byweekday=byweekday,
                    bymonthday=bymonthday,
                    dtstart=start_date,
                    bysetpos=bysetpos,
                    until=end_date,
                    count=count,
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
