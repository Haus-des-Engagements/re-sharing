from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from roomsharing.organizations.models import BookingPermission
from roomsharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import MessageForm
from .services import cancel_booking
from .services import create_booking_data
from .services import create_bookingmessage
from .services import filter_bookings_list
from .services import generate_single_booking
from .services import manager_cancel_booking
from .services import manager_confirm_booking
from .services import manager_confirm_rrule
from .services import manager_filter_bookings_list
from .services import manager_filter_invoice_bookings_list
from .services import save_booking
from .services import set_initial_booking_data
from .services import show_booking
from .services_recurrences import cancel_rrule_bookings
from .services_recurrences import create_rrule_and_occurrences
from .services_recurrences import get_rrule_bookings
from .services_recurrences import get_rrules_list
from .services_recurrences import manager_cancel_rrule
from .services_recurrences import manager_filter_rrules_list
from .services_recurrences import save_rrule


@require_http_methods(["GET"])
@login_required
def list_bookings_view(request):
    show_past_bookings = request.GET.get("show_past_bookings") or False
    status = request.GET.get("status") or "all"
    organization = request.GET.get("organization") or "all"
    page_number = request.GET.get("page", 1)
    hide_recurring_bookings = request.GET.get("hide_recurring_bookings") or False

    bookings, organizations = filter_bookings_list(
        organization,
        show_past_bookings,
        status,
        request.user,
        hide_recurring_bookings,
        page_number,
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


@require_http_methods(["GET"])
@login_required
def show_booking_view(request, booking):
    booking, activity_stream, access_code = show_booking(request.user, booking)

    return render(
        request,
        "bookings/show-booking.html",
        {
            "booking": booking,
            "activity_stream": activity_stream,
            "access_code": access_code,
        },
    )


@require_http_methods(["GET"])
@login_required
def list_recurrences_view(request):
    recurrences = get_rrules_list(request.user)

    return render(
        request, "bookings/list_recurrences.html", {"recurrences": recurrences}
    )


@require_http_methods(["GET"])
@login_required
def show_recurrence_view(request, rrule):
    rrule, bookings, is_cancelable = get_rrule_bookings(request.user, rrule)

    return render(
        request,
        "bookings/show_recurrence.html",
        {"bookings": bookings, "rrule": rrule, "is_cancelable": is_cancelable},
    )


@require_http_methods(["PATCH"])
@login_required
def cancel_rrule_bookings_view(request, rrule):
    rrule = cancel_rrule_bookings(request.user, rrule)
    messages.success(request, _("Successfully cancelled all future bookings."))

    return redirect("bookings:show-recurrence", rrule.slug)


@require_http_methods(["POST"])
@login_required
def create_bookingmessage_view(request, slug):
    form = MessageForm(data=request.POST)
    bookingmessage = create_bookingmessage(slug, form, request.user)

    return render(
        request,
        "bookings/partials/show_bookingmessage.html",
        {"message": bookingmessage},
    )


@require_http_methods(["PATCH"])
@login_required
def cancel_booking_view(request, slug):
    booking = cancel_booking(request.user, slug)

    return render(request, "bookings/partials/booking_item.html", {"booking": booking})


@require_http_methods(["PATCH"])
@login_required
def cancel_occurrence_view(request, slug):
    booking = cancel_booking(request.user, slug)

    return render(
        request, "bookings/partials/occurrence_item.html", {"booking": booking}
    )


@require_http_methods(["GET", "POST"])
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
        except IntegrityError:
            return HttpResponse(
                "Booking not possbile at the given date(s).", status=400
            )

        request.session.pop("booking_data", None)
        if booking.status == BookingStatus.CONFIRMED:
            messages.success(request, _("Booking created successfully!"))
        if booking.status == BookingStatus.PENDING:
            messages.info(
                request,
                _(
                    "Booking request created successfully! Please await our "
                    "confirmation. You will be notified by mail."
                ),
            )
        return redirect("bookings:show-booking", booking.slug)

    messages.error(request, _("Sorry, something went wrong. Please try again."))
    return redirect("bookings:create-booking")


@require_http_methods(["GET", "POST"])
@login_required
def preview_and_save_recurrence_view(request):
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")

    bookings, message, rrule, bookable = create_rrule_and_occurrences(booking_data)

    if request.method == "GET":
        return render(
            request,
            "bookings/preview-recurrence.html",
            {
                "message": message,
                "bookings": bookings,
                "rrule": rrule,
                "bookable": bookable,
            },
        )

    if request.method == "POST":
        bookings, rrule = save_rrule(request.user, bookings, rrule)
        request.session.pop("booking_data", None)
        messages.success(request, _("Recurrence created successfully!"))
        return redirect("bookings:show-recurrence", rrule.slug)

    messages.error(request, _("Sorry, something went wrong. Please try again."))
    return redirect("bookings:create-booking")


@require_http_methods(["GET", "POST"])
@login_required
def create_booking_data_form_view(request):
    if request.method == "GET":
        startdate = request.GET.get("startdate")
        starttime = request.GET.get("starttime")
        endtime = request.GET.get("endtime")
        room = request.GET.get("room")
        initial_data = set_initial_booking_data(endtime, startdate, starttime, room)
        user_has_bookingspermission = (
            BookingPermission.objects.filter(user=request.user)
            .filter(status=BookingPermission.Status.CONFIRMED)
            .exists()
        )

        form = BookingForm(user=request.user, initial=initial_data)
        return render(
            request,
            "bookings/create-booking.html",
            {"form": form, "user_has_bookingspermission": user_has_bookingspermission},
        )

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user)
        if form.is_valid():
            booking_data, rrule_string = create_booking_data(request.user, form)
            request.session["booking_data"] = booking_data
            if rrule_string:
                return redirect("bookings:preview-recurrence")
            return redirect("bookings:preview-booking")

    return render(request, "bookings/create-booking.html", {"form": form})


@require_http_methods(["GET"])
@staff_member_required
def manager_list_bookings_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the bookings for a room manager so that they can be confirmed or cancelled
    """
    show_past_bookings = request.GET.get("show_past_bookings") or False
    status = request.GET.get("status") or "1"
    organization = request.GET.get("organization") or "all"
    room = request.GET.get("room") or "all"
    date_string = request.GET.get("date") or None
    show_recurring_bookings = request.GET.get("show_recurring_bookings") or False

    bookings, organizations, rooms = manager_filter_bookings_list(
        organization,
        show_past_bookings,
        status,
        show_recurring_bookings,
        room,
        date_string,
    )

    context = {
        "bookings": bookings,
        "current_time": timezone.now(),
        "organizations": organizations,
        "statuses": BookingStatus.choices,
        "rooms": rooms,
    }

    if request.headers.get("HX-Request"):
        return render(request, "bookings/partials/manager_list_bookings.html", context)

    return render(request, "bookings/manager_list_bookings.html", context)


@require_http_methods(["PATCH"])
@staff_member_required
def manager_cancel_booking_view(request, booking_slug):
    booking = manager_cancel_booking(request.user, booking_slug)

    return render(
        request, "bookings/partials/manager_booking_item.html", {"booking": booking}
    )


@require_http_methods(["PATCH"])
@staff_member_required
def manager_confirm_booking_view(request, booking_slug):
    booking = manager_confirm_booking(request.user, booking_slug)
    return render(
        request, "bookings/partials/manager_booking_item.html", {"booking": booking}
    )


@require_http_methods(["GET"])
@staff_member_required
def manager_list_rrules_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the recurrences for a room manager so that they can be confirmed or cancelled
    """
    show_past_rrules = request.GET.get("show_past_rrules") or False
    status = request.GET.get("status") or 1
    organization = request.GET.get("organization") or "all"

    rrules, organizations = manager_filter_rrules_list(
        organization, show_past_rrules, status
    )

    context = {
        "rrules": rrules,
        "current_time": timezone.now(),
        "organizations": organizations,
        "statuses": BookingStatus.choices,
    }

    if request.headers.get("HX-Request"):
        return render(request, "bookings/partials/manager_list_rrules.html", context)

    return render(request, "bookings/manager_list_rrules.html", context)


@require_http_methods(["PATCH"])
@staff_member_required
def manager_cancel_rrule_view(request, rrule_uuid):
    rrule = manager_cancel_rrule(request.user, rrule_uuid)

    return render(
        request, "bookings/partials/manager_rrule_item.html", {"rrule": rrule}
    )


@require_http_methods(["PATCH"])
@staff_member_required
def manager_confirm_rrule_view(request, rrule_uuid):
    rrule = manager_confirm_rrule(request.user, rrule_uuid)

    return render(
        request, "bookings/partials/manager_rrule_item.html", {"rrule": rrule}
    )


@require_http_methods(["GET"])
@staff_member_required
def manager_filter_invoice_bookings_list_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the bookings with an invoice for a room manager so that they can be
    confirmed or cancelled
    """
    only_with_invoice_number = request.GET.get("only_with_invoice_number") or False
    organization = request.GET.get("organization", "all")
    invoice_number = request.GET.get("invoice_number") or None
    room = request.GET.get("room") or "all"
    bookings, organizations, rooms = manager_filter_invoice_bookings_list(
        organization, only_with_invoice_number, invoice_number, room
    )

    context = {
        "bookings": bookings,
        "organizations": organizations,
        "rooms": rooms,
    }

    if request.headers.get("HX-Request"):
        return render(request, "bookings/partials/manager_list_invoices.html", context)

    return render(request, "bookings/manager_list_invoices.html", context)
