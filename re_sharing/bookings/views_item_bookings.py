"""Views for lendable item bookings."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from re_sharing.organizations.models import Organization
from re_sharing.providers.decorators import manager_required

from .models import BookingGroup
from .services_item_bookings import cancel_booking_group
from .services_item_bookings import cancel_item_in_booking_group
from .services_item_bookings import create_item_booking_group
from .services_item_bookings import get_available_quantity
from .services_item_bookings import get_booking_group
from .services_item_bookings import get_booking_timespan
from .services_item_bookings import get_lendable_items
from .services_item_bookings import get_pickup_days
from .services_item_bookings import get_pickup_slots
from .services_item_bookings import get_return_days
from .services_item_bookings import get_return_slots
from .services_item_bookings import is_valid_pickup_date
from .services_item_bookings import is_valid_return_date
from .services_item_bookings import manager_cancel_booking_group
from .services_item_bookings import manager_cancel_item_in_booking_group
from .services_item_bookings import manager_confirm_booking_group


@require_http_methods(["GET", "POST"])
@login_required
@manager_required
def create_item_booking_view(request: HttpRequest) -> HttpResponse:
    """View for creating item bookings - shows item list and date selection."""
    # Get user's organizations
    user_organizations = request.user.get_organizations_of_user()

    if not user_organizations.exists():
        messages.warning(
            request,
            _(
                "You need to be a confirmed member of an organization "
                "to borrow equipment."
            ),
        )
        return redirect("bookings:list-bookings")

    items = get_lendable_items()
    pickup_slots = get_pickup_slots()
    return_slots = get_return_slots()
    pickup_days = get_pickup_days()
    return_days = get_return_days()

    # Get selected dates from form or session
    pickup_date = request.POST.get("pickup_date") or request.GET.get("pickup_date")
    return_date = request.POST.get("return_date") or request.GET.get("return_date")

    # Calculate availability if dates are selected
    items_with_availability = []
    if pickup_date and return_date:
        from datetime import date as date_type

        try:
            pickup_date_obj = date_type.fromisoformat(pickup_date)
            return_date_obj = date_type.fromisoformat(return_date)
            start_dt, end_dt = get_booking_timespan(pickup_date_obj, return_date_obj)

            for item in items:
                available = get_available_quantity(item, start_dt, end_dt)
                # Get daily rate from first compensation with a daily rate
                compensation = item.compensations_of_resource.filter(
                    daily_rate__isnull=False
                ).first()
                daily_rate = compensation.daily_rate if compensation else None
                items_with_availability.append(
                    {
                        "resource": item,
                        "available": available,
                        "total": item.quantity_available or 0,
                        "daily_rate": daily_rate,
                    }
                )
        except ValueError:
            pickup_date = None
            return_date = None
            items_with_availability = []
            for item in items:
                compensation = item.compensations_of_resource.filter(
                    daily_rate__isnull=False
                ).first()
                daily_rate = compensation.daily_rate if compensation else None
                items_with_availability.append(
                    {
                        "resource": item,
                        "available": item.quantity_available or 0,
                        "total": item.quantity_available or 0,
                        "daily_rate": daily_rate,
                    }
                )
    else:
        items_with_availability = []
        for item in items:
            compensation = item.compensations_of_resource.filter(
                daily_rate__isnull=False
            ).first()
            daily_rate = compensation.daily_rate if compensation else None
            items_with_availability.append(
                {
                    "resource": item,
                    "available": item.quantity_available or 0,
                    "total": item.quantity_available or 0,
                    "daily_rate": daily_rate,
                }
            )

    context = {
        "items": items_with_availability,
        "organizations": user_organizations,
        "pickup_slots": pickup_slots,
        "return_slots": return_slots,
        "pickup_days": pickup_days,
        "return_days": return_days,
        "pickup_date": pickup_date,
        "return_date": return_date,
    }

    if request.headers.get("HX-Request"):
        # Return just the items list for HTMX requests
        return render(request, "bookings/create-item-booking.html#item-list", context)

    return render(request, "bookings/create-item-booking.html", context)


@require_http_methods(["GET", "POST"])
@login_required
@manager_required
def preview_item_booking_view(request: HttpRequest) -> HttpResponse:  # noqa: C901, PLR0911, PLR0912
    """Preview item booking before confirmation."""
    if request.method == "GET":
        # Get data from session
        booking_data = request.session.get("item_booking_data")
        if not booking_data:
            return redirect("bookings:create-item-booking")

        return render(
            request,
            "bookings/preview-item-booking.html",
            {"booking_data": booking_data},
        )

    # POST - save booking data to session and show preview
    from datetime import date as date_type

    pickup_date = request.POST.get("pickup_date")
    return_date = request.POST.get("return_date")
    organization_id = request.POST.get("organization")

    if not pickup_date or not return_date or not organization_id:
        messages.error(request, _("Please fill in all required fields."))
        return redirect("bookings:create-item-booking")

    try:
        pickup_date_obj = date_type.fromisoformat(pickup_date)
        return_date_obj = date_type.fromisoformat(return_date)
        organization = Organization.objects.get(pk=organization_id)
    except (ValueError, Organization.DoesNotExist):
        messages.error(request, _("Invalid data provided."))
        return redirect("bookings:create-item-booking")

    # Validate dates
    if not is_valid_pickup_date(pickup_date_obj):
        messages.error(request, _("Pickup not available on this date."))
        return redirect("bookings:create-item-booking")

    if not is_valid_return_date(return_date_obj):
        messages.error(request, _("Return not available on this date."))
        return redirect("bookings:create-item-booking")

    if pickup_date_obj >= return_date_obj:
        messages.error(request, _("Return date must be after pickup date."))
        return redirect("bookings:create-item-booking")

    # Collect items
    items = []
    start_dt, end_dt = get_booking_timespan(pickup_date_obj, return_date_obj)
    num_days = (return_date_obj - pickup_date_obj).days + 1

    for key, value in request.POST.items():
        if key.startswith("quantity_") and value:
            try:
                resource_id = int(key.replace("quantity_", ""))
                quantity = int(value)
                if quantity > 0:
                    from re_sharing.resources.models import Resource

                    resource = Resource.objects.get(pk=resource_id)
                    available = get_available_quantity(resource, start_dt, end_dt)

                    if quantity > available:
                        messages.error(
                            request,
                            _("Only %(n)s available for %(item)s")
                            % {"n": available, "item": resource.name},
                        )
                        return redirect("bookings:create-item-booking")

                    # Get daily rate
                    compensations = resource.get_bookable_compensations(organization)
                    compensation = compensations.filter(
                        daily_rate__isnull=False
                    ).first()
                    daily_rate = compensation.daily_rate if compensation else 0

                    items.append(
                        {
                            "resource_id": resource_id,
                            "resource_name": resource.name,
                            "quantity": quantity,
                            "daily_rate": daily_rate,
                            "total": daily_rate * quantity * num_days,
                        }
                    )
            except (ValueError, Resource.DoesNotExist):
                continue

    if not items:
        messages.error(request, _("Please select at least one item."))
        return redirect("bookings:create-item-booking")

    # Store in session
    booking_data = {
        "pickup_date": pickup_date,
        "return_date": return_date,
        "pickup_time": start_dt.strftime("%H:%M"),
        "return_time": end_dt.strftime("%H:%M"),
        "organization_id": organization_id,
        "organization_name": organization.name,
        "items": items,
        "num_days": num_days,
        "total_amount": sum(item["total"] for item in items),
    }
    request.session["item_booking_data"] = booking_data

    return render(
        request, "bookings/preview-item-booking.html", {"booking_data": booking_data}
    )


@require_http_methods(["POST"])
@login_required
@manager_required
def confirm_item_booking_view(request: HttpRequest) -> HttpResponse:
    """Confirm and create the item booking."""
    from datetime import date as date_type

    booking_data = request.session.get("item_booking_data")
    if not booking_data:
        return redirect("bookings:create-item-booking")

    try:
        pickup_date = date_type.fromisoformat(booking_data["pickup_date"])
        return_date = date_type.fromisoformat(booking_data["return_date"])
        organization = Organization.objects.get(pk=booking_data["organization_id"])

        items = [
            {"resource_id": item["resource_id"], "quantity": item["quantity"]}
            for item in booking_data["items"]
        ]

        booking_group = create_item_booking_group(
            user=request.user,
            organization=organization,
            pickup_date=pickup_date,
            return_date=return_date,
            items=items,
        )

        # Clear session
        del request.session["item_booking_data"]

        messages.success(
            request,
            _("Equipment booking created successfully! Please await confirmation."),
        )
        return redirect("bookings:show-booking-group", slug=booking_group.slug)

    except (ValueError, PermissionDenied, ValidationError) as e:
        messages.error(request, str(e))
        return redirect("bookings:create-item-booking")


@require_http_methods(["GET"])
@login_required
@manager_required
def show_booking_group_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Show details of a BookingGroup."""
    booking_group = get_booking_group(request.user, slug)
    bookings = booking_group.bookings_of_bookinggroup.select_related(
        "resource", "compensation"
    )

    return render(
        request,
        "bookings/show-booking-group.html",
        {
            "booking_group": booking_group,
            "bookings": bookings,
        },
    )


@require_http_methods(["PATCH", "POST"])
@login_required
def cancel_booking_group_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Cancel an entire BookingGroup."""
    try:
        booking_group = cancel_booking_group(request.user, slug)
        messages.success(request, _("Equipment booking cancelled successfully."))
    except (PermissionDenied, ValidationError) as e:
        messages.error(request, str(e))

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/show-booking-group.html#booking-group-status",
            {"booking_group": booking_group},
        )

    return redirect("bookings:show-booking-group", slug=slug)


@require_http_methods(["PATCH", "POST"])
@login_required
@manager_required
def cancel_item_in_group_view(
    request: HttpRequest, slug: str, booking_id: int
) -> HttpResponse:
    """Cancel a single item in a BookingGroup."""
    try:
        booking = cancel_item_in_booking_group(request.user, slug, booking_id)
        messages.success(request, _("Item cancelled successfully."))
    except (PermissionDenied, ValidationError) as e:
        messages.error(request, str(e))

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/show-booking-group.html#booking-group-item",
            {"booking": booking},
        )

    return redirect("bookings:show-booking-group", slug=slug)


# Manager views


@require_http_methods(["GET"])
@manager_required
def manager_item_bookings_view(request: HttpRequest) -> HttpResponse:
    """Manager view for pending item BookingGroups."""

    booking_groups = BookingGroup.objects.all()

    status = request.GET.get("status", "1")  # Default to pending
    organization_search = request.GET.get("organization_search")

    if status != "all":
        booking_groups = booking_groups.filter(status=int(status))
    if organization_search:
        booking_groups = booking_groups.filter(
            organization__name__icontains=organization_search
        )

    context = {
        "booking_groups": booking_groups,
        "selected_status": status,
        "organization_search": organization_search,
    }

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_item_bookings.html#manager-item-bookings-list",
            context,
        )

    return render(request, "bookings/manager_item_bookings.html", context)


@require_http_methods(["GET"])
@manager_required
def manager_show_booking_group_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Manager detail view for a BookingGroup."""
    from django.shortcuts import get_object_or_404

    from .models import BookingGroup

    booking_group = get_object_or_404(BookingGroup, slug=slug)
    bookings = booking_group.bookings_of_bookinggroup.select_related(
        "resource", "compensation"
    )

    return render(
        request,
        "bookings/manager_show_booking_group.html",
        {
            "booking_group": booking_group,
            "bookings": bookings,
        },
    )


@require_http_methods(["PATCH", "POST"])
@manager_required
def manager_confirm_booking_group_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Manager confirms a BookingGroup."""
    try:
        booking_group = manager_confirm_booking_group(request.user, slug)
        messages.success(request, _("Equipment booking confirmed."))
    except PermissionDenied as e:
        messages.error(request, str(e))

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_item_bookings.html#manager-booking-group-item",
            {"booking_group": booking_group},
        )

    return redirect("bookings:manager-item-bookings")


@require_http_methods(["PATCH", "POST"])
@manager_required
def manager_cancel_booking_group_view(request: HttpRequest, slug: str) -> HttpResponse:
    """Manager cancels a BookingGroup."""
    try:
        booking_group = manager_cancel_booking_group(request.user, slug)
        messages.success(request, _("Equipment booking cancelled."))
    except PermissionDenied as e:
        messages.error(request, str(e))

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_item_bookings.html#manager-booking-group-item",
            {"booking_group": booking_group},
        )

    return redirect("bookings:manager-item-bookings")


@require_http_methods(["PATCH", "POST"])
@manager_required
def manager_cancel_item_in_group_view(
    request: HttpRequest, slug: str, booking_id: int
) -> HttpResponse:
    """Manager cancels a single item in a BookingGroup."""
    try:
        booking = manager_cancel_item_in_booking_group(request.user, slug, booking_id)
        messages.success(request, _("Item cancelled."))
    except PermissionDenied as e:
        messages.error(request, str(e))

    if request.headers.get("HX-Request"):
        return render(
            request,
            "bookings/manager_show_booking_group.html#manager-booking-item",
            {"booking": booking},
        )

    return redirect("bookings:manager-show-booking-group", slug=slug)
