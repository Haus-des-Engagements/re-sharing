from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.providers.decorators import manager_required
from re_sharing.resources.models import Resource
from re_sharing.utils.models import BookingStatus

from .forms import BookingForm
from .forms import MessageForm
from .models import Booking
from .services import MIN_ACCESS_CODE_SEARCH_LENGTH
from .services import FreeBookingsExhaustedError
from .services import bookings_webview
from .services import cancel_booking
from .services import create_booking_data
from .services import create_bookingmessage
from .services import default_access_code_window
from .services import filter_bookings_list
from .services import generate_booking
from .services import get_organizations_with_bundleable_bookings
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
from .services_pricing import get_free_bookings_remaining_after


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


def _redirect_to_booking_form(request, booking_data, error):
    """Send the user back to the form with the entered data after a pricing error."""
    messages.error(request, error.message)
    if booking_data.get("booking_id"):
        booking = get_object_or_404(Booking, id=booking_data["booking_id"])
        return redirect("bookings:update-booking", booking_slug=booking.slug)

    params = {
        "startdate": booking_data.get("start_date"),
        "starttime": (booking_data.get("start_time") or "")[:5],
        "endtime": (booking_data.get("end_time") or "")[:5],
        "resource": booking_data.get("resource"),
        "organization": booking_data.get("organization"),
        "title": booking_data.get("title"),
        "activity_description": booking_data.get("activity_description"),
        "attendees": booking_data.get("number_of_attendees"),
    }
    query = urlencode({key: value for key, value in params.items() if value})
    return redirect(f"{reverse('bookings:create-booking')}?{query}")


@require_http_methods(["GET", "POST"])
@login_required
def preview_and_save_booking_view(request):
    booking_data = request.session.get("booking_data")
    if not booking_data:
        return redirect("bookings:create-booking")

    try:
        booking = generate_booking(booking_data)
    except FreeBookingsExhaustedError as error:
        return _redirect_to_booking_form(request, booking_data, error)

    if request.method == "GET":
        return render(
            request,
            "bookings/preview-booking.html",
            {
                "booking": booking,
                "free_bookings_remaining_after": get_free_bookings_remaining_after(
                    booking
                ),
            },
        )

    if request.method == "POST":
        try:
            booking = save_booking(request.user, booking)
        except FreeBookingsExhaustedError as error:
            return _redirect_to_booking_form(request, booking_data, error)

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
        return render(request, "bookings/list_bookings.html#list-bookings", context)

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
    messages.success(
        request,
        _(
            "Successfully cancelled the entire booking series. "
            "All future bookings have been deleted."
        ),
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

    return render(
        request, "bookings/list_bookings.html#booking-item", {"booking": booking}
    )


@require_http_methods(["PATCH"])
@login_required
def cancel_booking_series_booking_view(request, slug):
    booking = cancel_booking(request.user, slug)

    return render(
        request,
        "bookings/show_booking_series.html#occurrence-item",
        {"booking": booking},
    )


@require_http_methods(["GET", "POST"])
@login_required
def preview_and_save_booking_series_view(request):
    booking_data = request.session.get("booking_data")
    if not booking_data:
        return redirect("bookings:create-booking")

    bookings, booking_series, bookable, pricing = create_booking_series_and_bookings(
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
                "pricing": pricing,
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
def list_bookings_webview(request: HttpRequest) -> HttpResponse:
    from django.conf import settings

    from .services import get_external_events

    location = request.GET.get("location") or "all"
    bookings, location = bookings_webview(location)

    # Fetch external events from ICS feed
    external_events = []
    if (
        hasattr(settings, "EXTERNAL_EVENTS_ICS_URL")
        and settings.EXTERNAL_EVENTS_ICS_URL
    ):
        external_events = get_external_events(settings.EXTERNAL_EVENTS_ICS_URL)

    return render(
        request,
        "bookings/list-bookings-webview.html",
        {
            "bookings": bookings,
            "date": timezone.now(),
            "location": location,
            "external_events": external_events,
        },
    )


@require_http_methods(["GET"])
@manager_required
def manager_list_bookings_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the bookings for a resource manager so that they can be confirmed or cancelled
    """
    show_past_bookings = request.GET.get("show_past_bookings") or False
    status = request.GET.get("status") or "1"
    organization_search = request.GET.get("organization_search")
    resource = request.GET.get("resource") or "all"
    location = request.GET.get("location") or "all"
    from_date_string = request.GET.get("from_date") or None
    until_date_string = request.GET.get("until_date") or None
    show_recurring_bookings = request.GET.get("show_recurring_bookings") or False
    access_code_search = (request.GET.get("access_code") or "").strip()
    show_all_dates = bool(request.GET.get("all_dates"))

    code_search_active = len(access_code_search) >= MIN_ACCESS_CODE_SEARCH_LENGTH
    access_code_window = None
    if code_search_active:
        # The status select always submits a value and unchecked boxes are
        # omitted entirely, so an explicit choice cannot be distinguished from
        # the form default. During a code search these three filters are
        # therefore always relaxed; the template disables the controls so the
        # page does not claim a filter it is not applying. Date inputs submit
        # an empty value when unset, so an explicit range stays honoured.
        status = "all"
        show_past_bookings = True
        show_recurring_bookings = True
        if not from_date_string and not until_date_string and not show_all_dates:
            access_code_window = default_access_code_window()
            from_date_string = access_code_window[0].isoformat()
            until_date_string = access_code_window[1].isoformat()

    bookings, resources, locations = manager_filter_bookings_list(
        organization_search,
        show_past_bookings,
        status,
        show_recurring_bookings,
        resource,
        location,
        from_date_string,
        until_date_string,
        request.user,
        access_code_search,
    )

    context = {
        "bookings": bookings,
        "current_time": timezone.now(),
        "statuses": BookingStatus.choices,
        "resources": resources,
        "locations": locations,
        "organization_search": organization_search,
        "selected_resource": resource,
        "selected_location": location,
        "selected_status": status,
        "selected_from_date": from_date_string,
        "selected_until_date": until_date_string,
        "show_past_bookings": show_past_bookings,
        "show_recurring_bookings": show_recurring_bookings,
        "access_code_search": access_code_search,
        "code_search_active": code_search_active,
        "access_code_window": access_code_window,
        "show_all_dates": show_all_dates,
        "is_htmx": bool(request.headers.get("HX-Request")),
    }

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_list_bookings.html#manager-list-bookings",
            context,
        )

    return render(request, "bookings/manager_list_bookings.html", context)


def _booking_row_context(request, booking):
    """Context for a single re-rendered booking row.

    The row partial renders an extra access code cell during a code search, so
    a row swapped in on its own has to know about the search or the table would
    lose a cell. The buttons carry the current code in their PATCH url.
    """
    access_code_search = (request.GET.get("access_code") or "").strip()
    return {
        "booking": booking,
        "access_code_search": access_code_search,
        "code_search_active": (
            len(access_code_search) >= MIN_ACCESS_CODE_SEARCH_LENGTH
        ),
    }


@require_http_methods(["PATCH"])
@manager_required
def manager_cancel_booking_view(request, booking_slug):
    booking = manager_cancel_booking(request.user, booking_slug)

    return render(
        request,
        "bookings/manager_list_bookings.html#manager-booking-item",
        _booking_row_context(request, booking),
    )


@require_http_methods(["PATCH"])
@manager_required
def manager_confirm_booking_view(request, booking_slug):
    booking = manager_confirm_booking(request.user, booking_slug)
    return render(
        request,
        "bookings/manager_list_bookings.html#manager-booking-item",
        _booking_row_context(request, booking),
    )


@require_http_methods(["GET"])
@manager_required
def manager_list_booking_series_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the recurrences for a resource manager so that they can be confirmed or
    cancelled
    """
    show_past_booking_series = request.GET.get("show_past_booking_series") or False
    status = request.GET.get("status") or 1
    organization_search = request.GET.get("organization_search")

    booking_series_list = manager_filter_booking_series_list(
        organization_search, show_past_booking_series, status
    )

    context = {
        "booking_series_list": booking_series_list,
        "current_time": timezone.now(),
        "organization_search": organization_search,
        "statuses": BookingStatus.choices,
    }

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_list_booking_series.html#manager-list-booking-series",
            context,
        )

    return render(request, "bookings/manager_list_booking_series.html", context)


@require_http_methods(["PATCH"])
@manager_required
def manager_cancel_booking_series_view(request, booking_series_uuid):
    booking_series = manager_cancel_booking_series(request.user, booking_series_uuid)

    return render(
        request,
        "bookings/manager_list_booking_series.html#manager-booking-series-item",
        {"booking_series": booking_series},
    )


@require_http_methods(["PATCH"])
@manager_required
def manager_confirm_booking_series_view(request, booking_series_uuid):
    booking_series = manager_confirm_booking_series(request.user, booking_series_uuid)

    return render(
        request,
        "bookings/manager_list_booking_series.html#manager-booking-series-item",
        {"booking_series": booking_series},
    )


@require_http_methods(["GET"])
@staff_member_required
def manager_filter_invoice_bookings_list_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the bookings with an invoice for a resource manager so that they can be
    confirmed or cancelled
    """
    invoice_filter = request.GET.get("invoice_filter", "without_invoice")
    organization_search = request.GET.get("organization_search")
    invoice_number = request.GET.get("invoice_number") or None
    resource = request.GET.get("resource") or "all"
    invoice_address_filter = request.GET.get("invoice_address_filter", "all")
    timespan_filter = request.GET.get("timespan_filter", "past")
    bookings, resources = manager_filter_invoice_bookings_list(
        organization_search,
        invoice_filter,
        invoice_number,
        resource,
        invoice_address_filter,
        timespan_filter,
    )

    orgs_with_bundleable = get_organizations_with_bundleable_bookings(
        organization_search
    )

    context = {
        "bookings": bookings,
        "organization_search": organization_search,
        "resources": resources,
        "invoice_number": invoice_number,
        "invoice_filter": invoice_filter,
        "invoice_address_filter": invoice_address_filter,
        "timespan_filter": timespan_filter,
        "now": timezone.now(),
        "orgs_with_bundleable": orgs_with_bundleable,
    }

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_list_invoices.html#manager-list-invoices",
            context,
        )

    return render(request, "bookings/manager_list_invoices.html", context)


@require_http_methods(["POST"])
@staff_member_required
def create_draft_invoice_view(request: HttpRequest, booking_slug: str) -> HttpResponse:
    """Trigger draft invoice creation in BuchhaltungsButler for a booking."""
    from .models import Booking
    from .tasks import create_draft_invoice

    booking = get_object_or_404(Booking, slug=booking_slug)

    if booking.invoice_number:
        return HttpResponse(_("Booking already has an invoice number."), status=400)

    if booking.timespan.upper > timezone.now():
        return HttpResponse(_("Booking has not yet taken place."), status=400)

    create_draft_invoice.enqueue(booking.id)

    return HttpResponse(
        '<span class="badge text-bg-success">Draft sent</span>',
    )


@require_http_methods(["POST"])
@staff_member_required
def create_einvoice_view(request: HttpRequest, booking_slug: str) -> HttpResponse:
    """Trigger e-invoice creation in BuchhaltungsButler for a booking."""
    from .models import Booking
    from .tasks import create_einvoice

    booking = get_object_or_404(Booking, slug=booking_slug)

    if booking.invoice_number:
        return HttpResponse(_("Booking already has an invoice number."), status=400)

    if booking.timespan.upper > timezone.now():
        return HttpResponse(_("Booking has not yet taken place."), status=400)

    create_einvoice.enqueue(booking.id)

    return HttpResponse(
        '<td colspan="9">'
        '<span class="badge text-bg-success">E-Invoice sent</span>'
        "</td>",
    )


@require_http_methods(["POST"])
@staff_member_required
def create_org_draft_invoice_view(
    request: HttpRequest, organization_slug: str
) -> HttpResponse:
    """Create a bundled draft invoice for all uninvoiced bookings of an org."""
    from .tasks import create_org_draft_invoice

    organization = get_object_or_404(Organization, slug=organization_slug)

    # Check that there are bundleable uninvoiced bookings
    bundleable_bookings = (
        Booking.objects.filter(
            organization=organization,
            status=BookingStatus.CONFIRMED,
            total_amount__gt=0,
            invoice_number="",
            timespan__endswith__lt=timezone.now(),
        )
        .exclude(resource__type=Resource.ResourceTypeChoices.LENDABLE_ITEM)
        .exclude(invoice_address__contains={"single_invoice": True})
    )

    if not bundleable_bookings.exists():
        return HttpResponse(
            _("No uninvoiced bookings for this organization."), status=400
        )

    create_org_draft_invoice.enqueue(organization.id)

    return HttpResponse(
        '<span class="badge text-bg-success">Draft sent</span>',
    )


@require_http_methods(["POST"])
@staff_member_required
def create_org_einvoice_view(
    request: HttpRequest, organization_slug: str
) -> HttpResponse:
    """Create a bundled e-invoice for all uninvoiced bookings of an org."""
    from .tasks import create_org_einvoice

    organization = get_object_or_404(Organization, slug=organization_slug)

    bundleable_bookings = (
        Booking.objects.filter(
            organization=organization,
            status=BookingStatus.CONFIRMED,
            total_amount__gt=0,
            invoice_number="",
            timespan__endswith__lt=timezone.now(),
        )
        .exclude(resource__type=Resource.ResourceTypeChoices.LENDABLE_ITEM)
        .exclude(invoice_address__contains={"single_invoice": True})
    )

    if not bundleable_bookings.exists():
        return HttpResponse(
            _("No uninvoiced bookings for this organization."), status=400
        )

    create_org_einvoice.enqueue(organization.id)

    return HttpResponse(
        '<span class="badge text-bg-success">E-Invoice sent</span>',
    )
