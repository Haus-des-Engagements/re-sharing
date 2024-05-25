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
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .forms import BookingForm
from .forms import BookingListForm
from .forms import RecurrenceForm
from .models import Booking
from .models import BookingMessage


@login_required
def booking_list_view(request):
    user_organizations = request.user.organizations.all()
    form = BookingListForm(request.POST or None, organizations=user_organizations)
    bookings = Booking.objects.filter(organization__in=user_organizations).filter(
        timespan__endswith__gte=timezone.now(),
    )

    return render(
        request,
        "bookings/bookings_list.html",
        {"bookings": bookings, "form": form},
    )


@login_required
def get_filtered_booking_list(request):
    user_organizations = request.user.organizations.all()
    form = BookingListForm(request.POST or None, organizations=user_organizations)
    bookings = Booking.objects.filter(organization__in=user_organizations)

    if form.is_valid():
        show_past_bookings = form.cleaned_data.get("show_past_bookings")
        status = form.cleaned_data["status"]
        organization = form.cleaned_data.get("organization")

        if not show_past_bookings:
            bookings = bookings.filter(timespan__endswith__gte=timezone.now())

        if organization != "all":
            bookings = bookings.filter(organization__slug=organization)

        if status != "all":
            bookings = bookings.filter(status=status)

        return render(
            request,
            "bookings/partials/bookings_list.html",
            {"bookings": bookings, "form": form},
        )

    return HttpResponse(
        f'<p class="error">Your form submission was unsuccessful. '
        f"Please would you correct the errors? The current errors: {form.errors}</p>",
    )


def booking_detail_view(request, slug):
    activity_stream = []
    booking = get_object_or_404(Booking, slug=slug)

    booking_logs = booking.history.all()
    activity_stream = list(booking_logs).copy()

    messages = BookingMessage.objects.filter(booking=booking)
    for message in messages:
        message_history_first = message.history.first()
        if message_history_first is not None:
            activity_stream.append(message_history_first)

    activity_stream.sort(key=lambda item: item.timestamp, reverse=False)

    return render(
        request,
        "bookings/booking_details.html",
        {"booking": booking, "activity_stream": activity_stream},
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
            booking = form.save(user=request.user)
            messages.success(request, _("Booking created successfully!"))
            return redirect("bookings:detail", booking.slug)

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
