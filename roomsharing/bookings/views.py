from datetime import datetime
from datetime import timedelta
from http import HTTPStatus

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
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from roomsharing.organizations.models import DefaultBookingStatus
from roomsharing.organizations.models import Membership
from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
from roomsharing.users.models import User
from roomsharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import BookingListForm
from .forms import MessageForm
from .forms import RecurrenceForm
from .models import Booking
from .models import BookingMessage


def is_member_of_booking_organization(user, booking):
    return (
        Membership.objects.filter(organization=booking.organization)
        .filter(user=booking.user)
        .filter(status=Membership.Status.CONFIRMED)
        .exists()
    )


@login_required
def list_bookings_view(request):
    organizations = (
        Organization.objects.filter(organization_of_membership__user=request.user)
        .filter(organization_of_membership__status=Membership.Status.CONFIRMED)
        .distinct()
    )
    form = BookingListForm(request.POST or None, organizations=organizations)
    bookings = Booking.objects.filter(organization__in=organizations).filter(
        timespan__endswith__gte=timezone.now(),
    )

    return render(
        request,
        "bookings/list_bookings.html",
        {"bookings": bookings, "form": form, "current_time": timezone.now()},
    )


@login_required
def filter_bookings_view(request):
    organizations = (
        Organization.objects.filter(organization_of_membership__user=request.user)
        .filter(organization_of_membership__status=Membership.Status.CONFIRMED)
        .distinct()
    )
    form = BookingListForm(request.POST or None, organizations=organizations)
    bookings = Booking.objects.filter(organization__in=organizations)

    if form.is_valid():
        show_past_bookings = form.cleaned_data.get("show_past_bookings")
        status = form.cleaned_data["status"]
        organization = form.cleaned_data.get("organization")

        if not show_past_bookings:
            bookings = bookings.filter(timespan__endswith__gte=timezone.now())

        if organization != "all":
            bookings = bookings.filter(organization__slug=organization)

        if status != "all":
            bookings = bookings.filter(status__in=status)

        return render(
            request,
            "bookings/partials/list_bookings.html",
            {"bookings": bookings, "form": form, "current_time": timezone.now()},
        )

    return HttpResponse(
        f'<p class="error">Your form submission was unsuccessful. '
        f"Please would you correct the errors? The current errors: {form.errors}</p>",
    )


@login_required
def show_booking_view(request, slug):
    activity_stream = []
    booking = get_object_or_404(Booking, slug=slug)

    if not is_member_of_booking_organization(request.user, booking):
        return HttpResponse(
            "You do not have permission to do this action",
            status=HTTPStatus.UNAUTHORIZED,
        )

    form = MessageForm()

    booking_logs = booking.history.filter(changes__has_key="status").exclude(
        changes__status__contains="None"
    )
    for log_entry in booking_logs:
        status_integer_old = int(log_entry.changes["status"][0])
        status_text_old = dict(BookingStatus.choices).get(status_integer_old)

        status_integer_new = int(log_entry.changes["status"][1])
        status_text_new = dict(BookingStatus.choices).get(status_integer_new)
        status_change_dict = {
            "date": log_entry.timestamp,
            "type": "status_change",
            "old_status": [status_integer_old, status_text_old],
            "new_status": [status_integer_new, status_text_new],
            "user": get_object_or_404(User, id=log_entry.actor_id),
        }
        activity_stream.append(status_change_dict)

    messages = BookingMessage.objects.filter(booking=booking)
    for message in messages:
        message_dict = {
            "date": message.created,
            "type": "message",
            "text": message.text,
            "user": message.user,
        }
        activity_stream.append(message_dict)

    activity_stream = sorted(activity_stream, key=lambda x: x["date"], reverse=True)

    return render(
        request,
        "bookings/show-booking.html",
        {
            "booking": booking,
            "activity_stream": activity_stream,
            "form": form,
            "current_time": timezone.now(),
        },
    )


@login_required
def write_bookingmessage(request, slug):
    booking = get_object_or_404(Booking, slug=slug)
    form = MessageForm(request.POST or None)

    if not is_member_of_booking_organization(request.user, booking):
        return HttpResponseForbidden("You do not have permission to do this action")

    if form.is_valid():
        message = form.save(commit=False)
        message.user = request.user
        message.booking = booking
        message.save()
        return render(
            request, "bookings/partials/show_bookingmessage.html", {"message": message}
        )

    return render(request, "bookings/show-booking.html", {"form": form})


@login_required
def cancel_booking(request, slug, from_page):
    booking = get_object_or_404(Booking, slug=slug)

    if not is_member_of_booking_organization(request.user, booking):
        return HttpResponseForbidden("You do not have permission to do this action")

    if booking.status in (BookingStatus.CONFIRMED, BookingStatus.PENDING):
        if booking.timespan.lower < timezone.now():
            return HttpResponse("You cannot cancel a booking that is in the past.")
        booking.status = BookingStatus.CANCELLED
        booking.save()

    if from_page == "detail":
        template_name = "bookings/partials/show_booking_item.html"
    else:
        template_name = "bookings/partials/list_bookings_item.html"

    return render(request, template_name, {"booking": booking})


@login_required
def create_booking_view(request):
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
        else:
            initial_data["startdate"] = datetime.strftime(
                timezone.now().date(), "%Y-%m-%d"
            )
        if starttime:
            initial_data["starttime"] = starttime
        if enddate:
            initial_data["enddate"] = enddate
        else:
            initial_data["enddate"] = initial_data["startdate"]
        if endtime:
            initial_data["endtime"] = endtime

        form = BookingForm(user=user, initial=initial_data)
        return render(request, "bookings/booking_form.html", {"form": form})

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user)
        if form.is_valid():
            booking = Booking()
            booking.user = request.user
            booking.title = form.cleaned_data["title"]
            booking.room = form.cleaned_data["room"]
            booking.timespan = form.cleaned_data["timespan"]
            booking.organization = form.cleaned_data["organization"]
            default_booking_status = DefaultBookingStatus.objects.filter(
                organization=booking.organization, room=booking.room
            )
            if default_booking_status.exists():
                booking.status = default_booking_status.first().status
            else:
                booking.status = BookingStatus.PENDING

            booking.save()
            message = form.cleaned_data["message"]
            if message:
                booking_message = BookingMessage(
                    booking=booking,
                    text=message,
                    user=request.user,
                )
                booking_message.save()

            messages.success(request, _("Booking created successfully!"))
            return redirect("bookings:show-booking", booking.slug)

    return render(request, "bookings/booking_form.html", {"form": form})


@login_required
def book_occurrences_view(request):
    if request.method == "POST":
        pass


@login_required
def recurrence_view(request):
    if request.method == "POST":
        form = RecurrenceForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data.get("start_date")
            frequency = form.cleaned_data.get("frequency")
            interval = form.cleaned_data.get("interval") or 1
            bysetpos = (
                [int(x) for x in form.cleaned_data.get("bysetpos")]
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

            recurrence_pattern = rrule(
                freq_dict[frequency],
                interval=interval,
                byweekday=byweekday,
                bymonthday=bymonthday,
                dtstart=start_date,
                bysetpos=bysetpos,
                until=end_date,
                count=count,
            )
            room = form.cleaned_data.get("room")
            duration = form.cleaned_data.get("duration")
            room = Room.objects.get(name=room)

            occurrences = list(recurrence_pattern)
            room_availability = []

            for occurrence in occurrences:
                start_datetime = occurrence
                end_datetime = start_datetime + timedelta(minutes=duration)
                timespan = (start_datetime, end_datetime)
                booking_overlap = Booking.objects.filter(
                    status=BookingStatus.CONFIRMED,
                    room=room,
                    timespan__overlap=timespan,
                ).exists()
                room_booked = booking_overlap
                room_availability.append(
                    {
                        "room_booked": room_booked,
                        "occurrence": occurrence,
                        "timespan": timespan,
                        "room": room.slug,
                    }
                )

            rrule_string = str(recurrence_pattern)
            return render(
                request,
                "bookings/recurrence.html",
                {
                    "occurrences": occurrences,
                    "rrule_string": rrule_string,
                    "room_availability": room_availability,
                },
            )
    if request.method == "GET":
        form = RecurrenceForm()

    return render(request, "bookings/recurrence.html", {"form": form})
