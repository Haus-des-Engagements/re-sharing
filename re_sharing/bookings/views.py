from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import MessageForm
from .models import Booking
from .services import cancel_booking
from .services import create_booking_data
from .services import create_bookingmessage
from .services import filter_bookings_list
from .services import generate_booking
from .services import manager_cancel_booking
from .services import manager_confirm_booking
from .services import manager_confirm_booking_series
from .services import manager_filter_bookings_list
from .services import manager_filter_invoice_bookings_list
from .services import save_booking
from .services import set_initial_booking_data
from .services import show_booking
from .services_booking_series import cancel_bookings_of_booking_series
from .services_booking_series import create_booking_series_and_bookings
from .services_booking_series import get_booking_series_list
from .services_booking_series import get_bookings_of_booking_series
from .services_booking_series import manager_cancel_booking_series
from .services_booking_series import manager_filter_booking_series_list
from .services_booking_series import save_booking_series


@require_http_methods(["GET", "POST"])
@login_required
def create_booking_data_form_view(request):
    if request.method == "GET":
        request_data = {
            "startdate": request.GET.get("startdate"),
            "starttime": request.GET.get("starttime"),
            "endtime": request.GET.get("endtime"),
            "resource": request.GET.get("resource"),
            "organization": request.GET.get("organization"),
            "attendees": request.GET.get("attendees"),
            "title": request.GET.get("title"),
            "activity_description": request.GET.get("activity_description"),
            "import_id": request.GET.get("import_id"),
        }

        initial_data = set_initial_booking_data(**request_data)
        # user needs at least to be confirmed for one confirmed organization
        user_has_bookingpermission = (
            BookingPermission.objects.filter(user=request.user)
            .filter(status=BookingPermission.Status.CONFIRMED)
            .filter(organization__status=Organization.Status.CONFIRMED)
            .exists()
        )

        form = BookingForm(user=request.user, initial=initial_data)
        return render(
            request,
            "bookings/create-booking.html",
            {"form": form, "user_has_bookingpermission": user_has_bookingpermission},
        )

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user)
        if form.is_valid():
            booking_data, rrule = create_booking_data(request.user, form)
            request.session["booking_data"] = booking_data
            if rrule:
                return redirect("bookings:preview-booking-series")
            return redirect("bookings:preview-booking")

    user_has_bookingpermission = (
        BookingPermission.objects.filter(user=request.user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .exists()
    )

    return render(
        request,
        "bookings/create-booking.html",
        {"form": form, "user_has_bookingpermission": user_has_bookingpermission},
    )


@require_http_methods(["GET", "POST"])
@login_required
def preview_and_save_booking_view(request):
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")

    booking = generate_booking(booking_data)
    if request.method == "GET":
        return render(
            request,
            "bookings/preview-booking.html",
            {"booking": booking},
        )

    if request.method == "POST":
        booking = save_booking(request.user, booking)

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


@login_required
def update_booking_view(request, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)
    if user_has_bookingpermission(request.user, booking):
        initial_data = {
            "starttime": booking.start_time.strftime("%H:%M"),
            "endtime": booking.end_time.strftime("%H:%M"),
            "startdate": booking.start_date.strftime("%Y-%m-%d"),
            "enddate": booking.end_date.strftime("%Y-%m-%d"),
        }
        form = BookingForm(instance=booking, user=request.user, initial=initial_data)
    else:
        raise PermissionDenied

    if request.method == "POST":
        form = BookingForm(data=request.POST, user=request.user, instance=booking)
        if form.is_valid():
            booking_data, rrule = create_booking_data(request.user, form)
            booking_data["booking_id"] = booking.id
            request.session["booking_data"] = booking_data
            return redirect("bookings:preview-booking")

    return render(
        request,
        "bookings/create-booking.html",
        {"form": form, "user_has_bookingpermission": True},
    )


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
def list_booking_series_view(request):
    booking_series_list = get_booking_series_list(request.user)

    return render(
        request,
        "bookings/list_booking_series.html",
        {"booking_series_list": booking_series_list},
    )


@require_http_methods(["GET"])
@login_required
def show_booking_series_view(request, booking_series):
    booking_series, bookings, is_cancelable = get_bookings_of_booking_series(
        request.user, booking_series
    )

    return render(
        request,
        "bookings/show_booking_series.html",
        {
            "bookings": bookings,
            "booking_series": booking_series,
            "is_cancelable": is_cancelable,
        },
    )


@require_http_methods(["PATCH"])
@login_required
def cancel_bookings_of_booking_series_view(request, booking_series):
    booking_series = cancel_bookings_of_booking_series(request.user, booking_series)
    booking_series, bookings, is_cancelable = get_bookings_of_booking_series(
        request.user, booking_series.slug
    )
    messages.success(request, _("Successfully cancelled all future bookings."))

    return render(
        request,
        "bookings/show_booking_series.html",
        {
            "bookings": bookings,
            "booking_series": booking_series,
            "is_cancelable": is_cancelable,
        },
    )


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
def cancel_booking_series_booking_view(request, slug):
    booking = cancel_booking(request.user, slug)

    return render(
        request, "bookings/partials/occurrence_item.html", {"booking": booking}
    )


@require_http_methods(["GET", "POST"])
@login_required
def preview_and_save_booking_series_view(request):
    booking_data = request.session["booking_data"]
    if not booking_data:
        return redirect("bookings:create-booking")

    bookings, booking_series, bookable = create_booking_series_and_bookings(
        booking_data
    )

    if request.method == "GET":
        return render(
            request,
            "bookings/preview-booking-series.html",
            {
                "bookings": bookings,
                "booking_series": booking_series,
                "bookable": bookable,
            },
        )

    if request.method == "POST":
        bookings, booking_series = save_booking_series(
            request.user, bookings, booking_series
        )
        request.session.pop("booking_data", None)
        messages.success(request, _("Booking series created successfully!"))
        return redirect("bookings:show-booking-series", booking_series.slug)

    messages.error(request, _("Sorry, something went wrong. Please try again."))
    return redirect("bookings:create-booking")


@require_http_methods(["GET"])
@staff_member_required
def manager_list_bookings_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the bookings for a resource manager so that they can be confirmed or cancelled
    """
    show_past_bookings = request.GET.get("show_past_bookings") or False
    status = request.GET.get("status") or "1"
    organization = request.GET.get("organization") or "all"
    resource = request.GET.get("resource") or "all"
    date_string = request.GET.get("date") or None
    show_recurring_bookings = request.GET.get("show_recurring_bookings") or False

    bookings, organizations, resources = manager_filter_bookings_list(
        organization,
        show_past_bookings,
        status,
        show_recurring_bookings,
        resource,
        date_string,
    )

    context = {
        "bookings": bookings,
        "current_time": timezone.now(),
        "organizations": organizations,
        "statuses": BookingStatus.choices,
        "resources": resources,
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
def manager_list_booking_series_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the recurrences for a resource manager so that they can be confirmed or
    cancelled
    """
    show_past_booking_series = request.GET.get("show_past_booking_series") or False
    status = request.GET.get("status") or 1
    organization = request.GET.get("organization") or "all"

    booking_series_list, organizations = manager_filter_booking_series_list(
        organization, show_past_booking_series, status
    )

    context = {
        "booking_series_list": booking_series_list,
        "current_time": timezone.now(),
        "organizations": organizations,
        "statuses": BookingStatus.choices,
    }

    if request.headers.get("HX-Request"):
        return render(
            request, "bookings/partials/manager_list_booking_series.html", context
        )

    return render(request, "bookings/manager_list_booking_series.html", context)


@require_http_methods(["PATCH"])
@staff_member_required
def manager_cancel_booking_series_view(request, booking_series_uuid):
    booking_series = manager_cancel_booking_series(request.user, booking_series_uuid)

    return render(
        request,
        "bookings/partials/manager_booking_series_item.html",
        {"booking_series": booking_series},
    )


@require_http_methods(["PATCH"])
@staff_member_required
def manager_confirm_booking_series_view(request, booking_series_uuid):
    booking_series = manager_confirm_booking_series(request.user, booking_series_uuid)

    return render(
        request,
        "bookings/partials/manager_booking_series_item.html",
        {"booking_series": booking_series},
    )


@require_http_methods(["GET"])
@staff_member_required
def manager_filter_invoice_bookings_list_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the bookings with an invoice for a resource manager so that they can be
    confirmed or cancelled
    """
    only_with_invoice_number = request.GET.get("only_with_invoice_number") or False
    organization = request.GET.get("organization", "all")
    invoice_number = request.GET.get("invoice_number") or None
    resource = request.GET.get("resource") or "all"
    bookings, organizations, resources = manager_filter_invoice_bookings_list(
        organization, only_with_invoice_number, invoice_number, resource
    )

    context = {
        "bookings": bookings,
        "organizations": organizations,
        "resources": resources,
        "invoice_number": invoice_number,
    }

    if request.headers.get("HX-Request"):
        return render(request, "bookings/partials/manager_list_invoices.html", context)

    return render(request, "bookings/manager_list_invoices.html", context)
