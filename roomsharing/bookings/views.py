from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from roomsharing.organizations.selectors import user_has_bookingpermission
from roomsharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import MessageForm
from .models import Booking
from .services import InvalidBookingOperationError
from .services import cancel_booking
from .services import create_rrule_string
from .services import filter_bookings_list
from .services import generate_bookings
from .services import get_booking_activity_stream
from .services import get_occurrences
from .services import get_recurrences_list
from .services import save_bookingmessage
from .services import save_bookings
from .services import set_initial_booking_data


@login_required
def list_bookings_view(request):
    show_past_bookings = request.GET.get("show_past_bookings") or False
    status = request.GET.get("status") or "all"
    organization = request.GET.get("organization") or "all"
    hide_recurring_bookings = request.GET.get("hide_recurring_bookings") or False

    bookings, organizations = filter_bookings_list(
        organization, show_past_bookings, status, request.user, hide_recurring_bookings
    )

    context = {
        "bookings": bookings,
        "current_time": timezone.now(),
        "organizations": organizations,
        "statuses": BookingStatus.choices,
    }

    if request.headers.get("HX-Request"):
        return render(request, "bookings/partials/list_bookings.html", context)

    return render(request, "bookings/list_bookings.html", context)


@login_required
def show_booking_view(request, booking):
    activity_stream, booking = get_booking_activity_stream(request.user, booking)

    return render(
        request,
        "bookings/show-booking.html",
        {
            "booking": booking,
            "activity_stream": activity_stream,
        },
    )


@login_required
def list_recurrences_view(request):
    recurrences = get_recurrences_list(request.user)

    return render(
        request, "bookings/list_recurrences.html", {"recurrences": recurrences}
    )


@login_required
def show_recurrence_view(request, rrule):
    rrule, bookings = get_occurrences(request.user, rrule)

    return render(
        request,
        "bookings/show_recurrence.html",
        {
            "bookings": bookings,
            "rrule": rrule,
        },
    )


@login_required
def write_bookingmessage(request, slug):
    booking = get_object_or_404(Booking, slug=slug)
    form = MessageForm(request.POST or None)

    if not user_has_bookingpermission(request.user, booking):
        return HttpResponseForbidden("You do not have permission to do this action")

    if form.is_valid():
        bookingmessage = save_bookingmessage(
            booking, form.cleaned_data["text"], request.user
        )
        return render(
            request,
            "bookings/partials/show_bookingmessage.html",
            {"message": bookingmessage},
        )

    return render(request, "bookings/show-booking.html", {"form": form})


@login_required
def cancel_booking_view(request, slug):
    try:
        booking = cancel_booking(request.user, slug)
    except (InvalidBookingOperationError, PermissionDenied) as e:
        return HttpResponse(e.message, status=e.status_code)

    return render(request, "bookings/partials/booking_item.html", {"booking": booking})


@login_required
def preview_booking_view(request):
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")

    bookings, message, rrule_string = generate_bookings(booking_data)
    if request.method == "GET":
        return render(
            request,
            "bookings/preview-booking.html",
            {"message": message, "bookings": bookings, "rrule_string": rrule_string},
        )
    if request.method == "POST":
        if user_has_bookingpermission(request.user, bookings[0]):
            save_bookings(bookings, message, rrule_string)

            request.session.pop("booking_data", None)
            messages.success(request, _("Bookings created successfully!"))

            if len(bookings) == 1:
                return redirect("bookings:show-booking", bookings[0].slug)

            return redirect("bookings:list-bookings")

        messages.warning(request, _("You dont have the required permissions."))
        return redirect("bookings:create-booking")

    messages.error(request, _("Sorry, something went wrong. Please try again."))
    return redirect("bookings:create-booking")


@login_required
def create_booking_view(request):
    if request.method == "GET":
        startdate = request.GET.get("startdate")
        starttime = request.GET.get("starttime")
        endtime = request.GET.get("endtime")
        initial_data = set_initial_booking_data(endtime, startdate, starttime)

        form = BookingForm(user=request.user, initial=initial_data)
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
                "start_date": form.cleaned_data["startdate"].isoformat(),
                "start_time": form.cleaned_data["starttime"].isoformat(),
                "end_time": form.cleaned_data["endtime"].isoformat(),
                "user": request.user.slug,
            }

            if form.cleaned_data["rrule_repetitions"] != "NO_REPETITIONS":
                rrule_string = create_rrule_string(form.cleaned_data)
                request.session["booking_data"]["rrule_string"] = rrule_string

            return redirect("bookings:preview-booking")

    return render(request, "bookings/create-booking.html", {"form": form})
