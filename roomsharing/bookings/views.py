from datetime import datetime
from http import HTTPStatus

from dateutil.parser import isoparse
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
from dateutil.rrule import rrulestr
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.models import DefaultBookingStatus
from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
from roomsharing.users.models import User
from roomsharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import BookingListForm
from .forms import MessageForm
from .models import Booking
from .models import BookingMessage


def is_member_of_booking_organization(user, booking):
    return (
        BookingPermission.objects.filter(organization=booking.organization)
        .filter(user=booking.user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .exists()
    )


@login_required
def list_bookings_view(request):
    organizations = (
        Organization.objects.filter(
            organization_of_bookingpermission__user=request.user
        )
        .filter(
            organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED
        )
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
        Organization.objects.filter(
            organization_of_bookingpermission__user=request.user
        )
        .filter(
            organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED
        )
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


def create_rrule_string(cleaned_data):
    rrule_repetitions = cleaned_data["rrule_repetitions"]
    rrule_ends = cleaned_data["rrule_ends"]
    rrule_ends_count = cleaned_data.get("rrule_ends_count")
    rrule_ends_enddate = cleaned_data.get("rrule_ends_enddate")
    rrule_daily_interval = cleaned_data["rrule_daily_interval"]
    rrule_weekly_interval = cleaned_data["rrule_weekly_interval"]
    rrule_weekly_byday = cleaned_data["rrule_weekly_byday"]
    rrule_monthly_interval = cleaned_data["rrule_monthly_interval"]
    rrule_monthly_bydate = cleaned_data["rrule_monthly_bydate"]
    rrule_monthly_byday = cleaned_data["rrule_monthly_byday"]
    startdate = cleaned_data["startdate"]

    if rrule_ends == "AFTER_TIMES":
        count = rrule_ends_count
        rrule_enddate = None
    else:
        count = None
        rrule_enddate = rrule_ends_enddate

    byweekday, bymonthday = None, None
    weekdays_dict = {
        "MO": MO,
        "TU": TU,
        "WE": WE,
        "TH": TH,
        "FR": FR,
        "SA": SA,
        "SU": SU,
    }

    if rrule_repetitions == "DAILY":
        interval = rrule_daily_interval

    if rrule_repetitions == "WEEKLY":
        interval = rrule_weekly_interval
        byweekday = rrule_weekly_byday
        byweekday = [weekdays_dict.get(day) for day in byweekday]

    if rrule_repetitions == "MONTHLY_BY_DAY":
        interval = rrule_monthly_interval
        byweekday_str = rrule_monthly_byday
        byweekday = []
        for day in byweekday_str:
            weekday, week_number = day.split("(")
            week_number = int(week_number.strip(")"))
            byweekday.append(weekdays_dict[weekday](week_number))

    if rrule_repetitions == "MONTHLY_BY_DATE":
        interval = rrule_monthly_interval
        bymonthday_str = rrule_monthly_bydate
        bymonthday = [int(x) for x in bymonthday_str]

    frequency_dict = {
        "DAILY": DAILY,
        "WEEKLY": WEEKLY,
        "MONTHLY_BY_DAY": MONTHLY,
        "MONTHLY_BY_DATE": MONTHLY,
    }

    recurrence_pattern = rrule(
        frequency_dict[rrule_repetitions],
        interval=interval,
        byweekday=byweekday,
        bymonthday=bymonthday,
        dtstart=startdate,
        bysetpos=None,
        until=rrule_enddate,
        count=count,
    )
    return str(recurrence_pattern)


def get_default_booking_status(organization, room):
    default_booking_status = DefaultBookingStatus.objects.filter(
        organization=organization, room=room
    )
    if default_booking_status.exists():
        return default_booking_status.first().status

    return BookingStatus.PENDING


@login_required
def preview_booking_view(request):  # noqa: C901
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")
    message = booking_data["message"]
    timespan = booking_data["timespan"]
    timespan = (isoparse(timespan[0]), isoparse(timespan[1]))
    user = request.user
    title = booking_data["title"]
    room = get_object_or_404(Room, slug=booking_data["room"])
    organization = get_object_or_404(Organization, slug=booking_data["organization"])
    status = get_default_booking_status(organization, room)

    bookings = []

    if booking_data.get("rrule_string"):
        occurrences = list(rrulestr(booking_data["rrule_string"]))
        starttime = timespan[0].time()
        endtime = timespan[1].time()
        for occurrence in occurrences:
            start_datetime = timezone.make_aware(
                datetime.combine(occurrence, starttime)
            )
            end_datetime = timezone.make_aware(datetime.combine(occurrence, endtime))

            booking = Booking(
                user=user,
                title=title,
                room=room,
                timespan=(start_datetime, end_datetime),
                organization=organization,
                status=status,
            )
            booking_overlap = (
                Booking.objects.all()
                .filter(
                    status=BookingStatus.CONFIRMED,
                    room=booking.room,
                    timespan__overlap=(start_datetime, end_datetime),
                )
                .exists()
            )
            booking.room_booked = booking_overlap
            bookings.append(booking)

    else:
        booking = Booking(
            user=user,
            title=title,
            room=room,
            timespan=timespan,
            organization=organization,
            status=status,
        )
        bookings.append(booking)

    if request.method == "GET":
        return render(
            request,
            "bookings/preview-booking.html",
            {
                "message": message,
                "bookings": bookings,
            },
        )

    if request.method == "POST":
        if is_member_of_booking_organization(request.user, booking.organization):
            for booking in bookings:
                if booking.room_booked is False:
                    booking.save()
                    if message:
                        booking_message = BookingMessage(
                            booking=booking,
                            text=message,
                            user=request.user,
                        )
                        booking_message.save()
            request.session.pop("booking_data", None)

            messages.success(request, _("Bookings created successfully!"))
            if len(bookings) == 1:
                return redirect("bookings:show-booking", booking.slug)

            return redirect("bookings:list-bookings")

    return redirect("bookings:create-booking")


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
        return render(request, "bookings/create-booking.html", {"form": form})

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user)
        if form.is_valid():
            if isinstance(form.cleaned_data["timespan"], tuple):
                timespan_start, timespan_end = form.cleaned_data["timespan"]
                timespan = (timespan_start.isoformat(), timespan_end.isoformat())

            request.session["booking_data"] = {
                "title": form.cleaned_data["title"],
                "room": form.cleaned_data["room"].slug,
                "timespan": timespan,
                "organization": form.cleaned_data["organization"].slug,
                "message": form.cleaned_data["message"],
            }

            if form.cleaned_data["rrule_repetitions"] != "NO_REPETITIONS":
                rrule_string = create_rrule_string(form.cleaned_data)
                request.session["booking_data"]["rrule_string"] = rrule_string

            return redirect("bookings:preview-booking")

    return render(request, "bookings/create-booking.html", {"form": form})
