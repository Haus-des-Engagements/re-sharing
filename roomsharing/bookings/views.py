from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from roomsharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import MessageForm
from .services import InvalidBookingOperationError
from .services import cancel_booking
from .services import cancel_rrule_bookings
from .services import create_booking_data
from .services import create_bookingmessage
from .services import filter_bookings_list
from .services import generate_recurrence
from .services import generate_single_booking
from .services import get_occurrences
from .services import get_recurrences_list
from .services import save_booking
from .services import save_recurrence
from .services import set_initial_booking_data
from .services import show_booking


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
    try:
        booking, activity_stream, access_code = show_booking(request.user, booking)
    except PermissionDenied as e:
        return HttpResponse(str(e), status=HTTPStatus.FORBIDDEN)

    return render(
        request,
        "bookings/show-booking.html",
        {
            "booking": booking,
            "activity_stream": activity_stream,
            "access_code": access_code,
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
    rrule, bookings, is_cancelable = get_occurrences(request.user, rrule)

    return render(
        request,
        "bookings/show_recurrence.html",
        {"bookings": bookings, "rrule": rrule, "is_cancelable": is_cancelable},
    )


@login_required
def cancel_rrule_bookings_view(request, rrule):
    try:
        rrule = cancel_rrule_bookings(request.user, rrule)
    except (InvalidBookingOperationError, PermissionDenied) as e:
        return HttpResponse(e.message, status=e.status_code)

    messages.success(request, _("Successfully cancelled all future bookings."))
    return redirect("bookings:show-recurrence", rrule.uuid)


@login_required
def create_bookingmessage_view(request, slug):
    try:
        form = MessageForm(data=request.POST)
        bookingmessage = create_bookingmessage(slug, form, request.user)

    except (InvalidBookingOperationError, PermissionDenied) as e:
        return HttpResponse(e.message, status=e.status_code)

    return render(
        request,
        "bookings/partials/show_bookingmessage.html",
        {"message": bookingmessage},
    )


@login_required
def cancel_booking_view(request, slug):
    try:
        booking = cancel_booking(request.user, slug)
    except (InvalidBookingOperationError, PermissionDenied) as e:
        return HttpResponse(e.message, status=e.status_code)

    message = _("Successfully cancelled.")

    return render(request, "bookings/partials/booking_item.html", {"booking": booking})

    return HttpResponse(
        f'{message} <span id="status-{booking.slug}" '
        f'hx-swap-oob="true" class="fs-6 badge text-bg-status-{booking.status}">'
        f"{booking.get_status_display()}</span>"
    )


@login_required
def preview_and_save_booking_view(request):
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")

    booking, message = generate_single_booking(booking_data)
    if request.method == "GET":
        return render(
            request,
            "bookings/preview-booking.html",
            {"message": message, "booking": booking},
        )

    if request.method == "POST":
        try:
            booking = save_booking(request.user, booking, message)
        except PermissionDenied as e:
            return HttpResponse(e.message, status=e.status_code)
        except IntegrityError:
            return HttpResponse(
                "Booking not possbile at the given date(s).", status=400
            )

        request.session.pop("booking_data", None)
        messages.success(request, _("Booking created successfully!"))
        return redirect("bookings:show-booking", booking.slug)

    messages.error(request, _("Sorry, something went wrong. Please try again."))
    return redirect("bookings:create-booking")


@login_required
def preview_and_save_recurrence_view(request):
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")

    try:
        bookings, message, rrule, bookable, rrule_total_amount = generate_recurrence(
            booking_data
        )
    except PermissionDenied as e:
        return HttpResponse(e.message, status=e.status_code)

    if request.method == "GET":
        return render(
            request,
            "bookings/preview-recurrence.html",
            {
                "message": message,
                "bookings": bookings,
                "rrule": rrule,
                "bookable": bookable,
                "rrule_total_amount": rrule_total_amount,
            },
        )

    if request.method == "POST":
        try:
            bookings, rrule = save_recurrence(request.user, bookings, message, rrule)
        except PermissionDenied as e:
            return HttpResponse(e.message, status=e.status_code)

        request.session.pop("booking_data", None)
        messages.success(request, _("Recurrence created successfully!"))
        return redirect("bookings:show-recurrence", rrule.uuid)

    messages.error(request, _("Sorry, something went wrong. Please try again."))
    return redirect("bookings:create-booking")


@login_required
def create_booking_data_form_view(request):
    if request.method == "GET":
        startdate = request.GET.get("startdate")
        starttime = request.GET.get("starttime")
        endtime = request.GET.get("endtime")
        room = request.GET.get("room")
        initial_data = set_initial_booking_data(endtime, startdate, starttime, room)

        form = BookingForm(user=request.user, initial=initial_data)
        return render(request, "bookings/create-booking.html", {"form": form})

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user)
        if form.is_valid():
            booking_data, rrule_string = create_booking_data(request.user, form)
            request.session["booking_data"] = booking_data
            if rrule_string:
                return redirect("bookings:preview-recurrence")
            return redirect("bookings:preview-booking")

    return render(request, "bookings/create-booking.html", {"form": form})
