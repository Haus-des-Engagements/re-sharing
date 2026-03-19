from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.db.models import Q
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django_ical.views import ICalFeed

from re_sharing.bookings.models import Booking
from re_sharing.organizations.models import Organization
from re_sharing.providers.decorators import manager_required
from re_sharing.resources.forms import CompensationEditForm
from re_sharing.resources.forms import ResourceEditForm
from re_sharing.resources.forms import ResourceImageForm
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Location
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceImage
from re_sharing.resources.models import ResourceRestriction
from re_sharing.resources.services import filter_resources
from re_sharing.resources.services import get_user_accessible_locations
from re_sharing.resources.services import planner
from re_sharing.resources.services import show_resource
from re_sharing.utils.models import BookingStatus


@require_http_methods(["GET"])
def list_resources_view(request):
    persons_count = request.GET.get("persons_count")
    start_date = request.GET.get("start_date")
    start_time = request.GET.get("start_time")
    duration = request.GET.get("duration", "60")  # Default to 60 minutes (1 hour)
    location_slug = request.GET.get("location")
    resource_type = request.GET.get("type", "room")  # Default to room

    # Combine date and time into datetime string if both are provided
    start_datetime = None
    if start_date and start_time:
        start_datetime = f"{start_date}T{start_time}"

    resources = filter_resources(
        request.user,
        persons_count,
        start_datetime,
        location_slug,
        duration,
        resource_type,
    )
    locations = get_user_accessible_locations(request.user)

    # Create duration options from 30 minutes to 8 hours in 30-minute steps
    duration_options = []
    for minutes in range(30, 481, 30):  # 30 to 480 minutes (8 hours)
        hours = minutes // 60
        mins = minutes % 60
        label = f"{hours}:00h" if mins == 0 else f"{hours}:{mins:02d}h"
        duration_options.append({"value": minutes, "label": label})

    # Create time options from 7:00 to 23:00 in 30-minute steps
    start_hour = 7
    end_hour = 24
    last_hour = 23
    minute_step = 30

    time_options = []
    for hour in range(start_hour, end_hour):
        for minute in [0, minute_step]:
            if hour == last_hour and minute == minute_step:
                break  # Stop at 23:00
            time_value = f"{hour:02d}:{minute:02d}"
            time_options.append({"value": time_value, "label": time_value})

    # Calculate end time if both start time and duration are provided
    selected_end_time = None
    if start_time:
        try:
            start_dt = datetime.strptime(start_time, "%H:%M")  # noqa: DTZ007
            end_dt = start_dt + timedelta(minutes=int(duration))
            selected_end_time = end_dt.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

    context = {
        "resources": resources,
        "locations": locations,
        "duration_options": duration_options,
        "selected_duration": int(duration),
        "time_options": time_options,
        "selected_date": start_date,
        "selected_time": start_time,
        "selected_end_time": selected_end_time,
    }
    if request.headers.get("HX-Request"):
        return render(request, "resources/list_resources.html#resource-list", context)

    return render(request, "resources/list_resources.html", context)


@require_http_methods(["GET"])
def show_resource_view(request, resource_slug):
    date_string = request.GET.get("date")
    resource, timeslots, weekdays, dates, compensations, restrictions = show_resource(
        resource_slug, date_string
    )

    context = {
        "resource": resource,
        "weekdays": weekdays,
        "timeslots": timeslots,
        "dates": dates,
        "compensations": compensations,
        "restrictions": restrictions,
    }
    if request.headers.get("HX-Request"):
        return render(
            request, "resources/show_resource.html#weekly-bookings-table", context
        )

    return render(request, "resources/show_resource.html", context)


@require_http_methods(["GET"])
def planner_view(request):
    date_string = request.GET.get("date")
    selected_nb_of_days = int(request.GET.get("selected_nb_of_days", "3"))
    selected_resources_slugs = request.GET.getlist("resources")
    location_slug = request.GET.get("location")

    if request.user.is_authenticated:
        resources = request.user.get_resources()
    else:
        resources = Resource.objects.filter(is_private=False)
    resources = resources.filter(
        type__in=[
            Resource.ResourceTypeChoices.ROOM,
            Resource.ResourceTypeChoices.PARKING_LOT,
        ]
    )
    # Filter resources by location if specified
    if location_slug:
        resources = resources.filter(location__slug=location_slug)

    if selected_resources_slugs:
        selected_resources = resources.filter(slug__in=selected_resources_slugs)
    else:
        selected_resources = resources

    grouped_resources = {}
    for access_type in resources.values_list("access__name", flat=True).distinct():
        grouped_resources[access_type] = resources.filter(access__name=access_type)

    # Get locations that the user has access to
    locations = get_user_accessible_locations(request.user)

    _resource, timeslots, weekdays, dates, planner_data = planner(
        request.user, date_string, selected_nb_of_days, selected_resources
    )
    context = {
        "resources": resources,
        "grouped_resources": grouped_resources,
        "selected_resources": selected_resources,
        "timeslots": timeslots,
        "dates": dates,
        "weekdays": weekdays,
        "planner_data": planner_data,
        "nb_of_days": range(1, 15),
        "selected_nb_of_days": selected_nb_of_days,
        "locations": locations,
        "location_slug": location_slug,
    }

    if (
        request.headers.get("HX-Request")
        and request.headers.get("partial") == "selection_and_table"
    ):
        return render(
            request, "resources/multi_planner.html#selection-and-table", context
        )
    if (
        request.headers.get("HX-Request")
        and request.headers.get("partial") == "planner-table"
    ):
        return render(
            request,
            "resources/multi_planner.html#multi-planner-table",
            context,
        )
    return render(request, "resources/multi_planner.html", context)


@require_http_methods(["POST"])
@login_required
def get_compensations(request, selected_compensation=None):
    resource_id = request.POST.get("resource")
    organization_id = request.POST.get("organization")
    starttime = request.POST.get("starttime")
    startdate = request.POST.get("startdate")
    bookable = True
    if not resource_id or not organization_id:
        return render(
            request,
            "bookings/partials/compensations.html",
            {"compensations": [], "bookable": bookable},
        )
    resource = get_object_or_404(Resource, id=resource_id)
    organization = get_object_or_404(Organization, id=organization_id)
    org_groups = organization.organization_groups.all()

    start_time = time.fromisoformat(starttime)
    start_date = date.fromisoformat(startdate)

    # Check if there are any active restrictions that apply to this resource,
    # organization, and datetime
    booking_datetime = datetime.combine(start_date, start_time)

    # Get all active restrictions that apply to this resource
    restrictions = ResourceRestriction.objects.filter(
        is_active=True, resources=resource
    )

    # Check if any of the restrictions apply to this organization and datetime
    restriction_message = None
    for restriction in restrictions:
        if restriction.applies_to_organization(
            organization
        ) and restriction.applies_to_datetime(booking_datetime):
            bookable = False
            restriction_message = restriction.message
            break

    compensations = (
        Compensation.objects.filter(is_active=True)
        .filter(Q(resource=resource) | Q(resource=None))
        .filter(Q(organization_groups__in=org_groups) | Q(organization_groups=None))
    )
    if selected_compensation in compensations.values_list("id", flat=True):
        selected_compensation = get_object_or_404(
            Compensation, id=selected_compensation
        )
    else:
        selected_compensation = 1

    return render(
        request,
        "bookings/partials/compensations.html",
        {
            "compensations": compensations,
            "selected_compensation": selected_compensation,
            "bookable": bookable,
            "restriction_message": restriction_message,
        },
    )


class ResourceIcalFeed(ICalFeed):
    """ICS calendar feed for a specific resource showing daily bookings."""

    timezone = "UTC"

    def get_object(self, request, resource_slug):
        return get_object_or_404(Resource, slug=resource_slug)

    def file_name(self, obj):
        return f"{obj.slug}.ics"

    def title(self, obj):
        return f"{obj.name} - Bookings"

    def description(self, obj):
        return f"Booking schedule for {obj.name}"

    def items(self, obj):
        return Booking.objects.filter(
            resource=obj,
            start_date=timezone.now().date(),
            status=BookingStatus.CONFIRMED,
        ).order_by("start_date", "start_time")

    def item_title(self, item):
        if item.organization.public_name:
            return f"{item.organization.public_name}"
        return f"{item.organization.name}"

    def item_start_datetime(self, item):
        return item.timespan.lower

    def item_end_datetime(self, item):
        return item.timespan.upper

    def item_description(self, item):
        domain = Site.objects.get_current().domain
        return f"https://{domain}{item.get_absolute_url()}"

    def item_link(self, item):
        domain = Site.objects.get_current().domain
        return f"https://{domain}{item.get_absolute_url()}"


# ---------------------------------------------------------------------------
# Manager resource views
# ---------------------------------------------------------------------------


@require_http_methods(["GET"])
@manager_required
def manager_list_resources_view(request: HttpRequest) -> HttpResponse:
    """Manager list view for all resources with type and location filters."""
    resources = Resource.objects.select_related("location").order_by("name")

    type_filter = request.GET.get("type", "")
    location_filter = request.GET.get("location", "")

    if type_filter:
        resources = resources.filter(type=type_filter)
    if location_filter:
        resources = resources.filter(location__slug=location_filter)

    locations = Location.objects.order_by("name")

    context = {
        "resources": resources,
        "locations": locations,
        "selected_type": type_filter,
        "selected_location": location_filter,
        "resource_type_choices": Resource.ResourceTypeChoices.choices,
    }

    if request.headers.get("HX-Request"):
        return render(
            request,
            "resources/manager_list_resources.html#resource-list",
            context,
        )

    return render(request, "resources/manager_list_resources.html", context)


@require_http_methods(["GET"])
@manager_required
def manager_show_resource_view(
    request: HttpRequest, resource_slug: str
) -> HttpResponse:
    """Manager detail view for a single resource."""
    resource = get_object_or_404(Resource, slug=resource_slug)
    compensations = resource.compensations_of_resource.all()
    linked_ids = compensations.values_list("pk", flat=True)
    available_compensations = Compensation.objects.exclude(pk__in=linked_ids).order_by(
        "name"
    )
    images = resource.resourceimages_of_resource.all()
    image_form = ResourceImageForm()

    return render(
        request,
        "resources/manager_show_resource.html",
        {
            "resource": resource,
            "compensations": compensations,
            "available_compensations": available_compensations,
            "images": images,
            "image_form": image_form,
        },
    )


@require_http_methods(["GET", "POST"])
@manager_required
def manager_edit_resource_view(
    request: HttpRequest, resource_slug: str
) -> HttpResponse:
    """Manager view to edit a Resource's core fields."""
    resource = get_object_or_404(Resource, slug=resource_slug)

    if request.method == "POST":
        form = ResourceEditForm(request.POST, instance=resource)
        if form.is_valid():
            resource = form.save()
            messages.success(request, _("Resource updated."))
            return redirect(
                "resources:manager-show-resource", resource_slug=resource.slug
            )
    else:
        form = ResourceEditForm(instance=resource)

    return render(
        request,
        "resources/manager_edit_resource.html",
        {"form": form, "resource": resource},
    )


@require_http_methods(["GET", "POST"])
@manager_required
def manager_edit_compensation_view(
    request: HttpRequest, compensation_id: int
) -> HttpResponse:
    """Manager view to edit a Compensation."""
    compensation = get_object_or_404(Compensation, pk=compensation_id)
    affected_resources = compensation.resource.all()

    if request.method == "POST":
        form = CompensationEditForm(request.POST, instance=compensation)
        if form.is_valid():
            form.save()
            messages.success(request, _("Compensation updated."))
            # Go back to the resource that linked here, if provided
            back_slug = request.GET.get("resource")
            if back_slug:
                return redirect(
                    "resources:manager-show-resource", resource_slug=back_slug
                )
            return redirect("resources:manager-list-resources")
    else:
        form = CompensationEditForm(instance=compensation)

    return render(
        request,
        "resources/manager_edit_compensation.html",
        {
            "form": form,
            "compensation": compensation,
            "affected_resources": affected_resources,
        },
    )


@require_http_methods(["POST"])
@manager_required
def manager_link_compensation_view(
    request: HttpRequest, resource_slug: str
) -> HttpResponse:
    """Link an existing compensation to a resource."""
    resource = get_object_or_404(Resource, slug=resource_slug)
    compensation_id = request.POST.get("compensation_id")
    compensation = get_object_or_404(Compensation, pk=compensation_id)
    compensation.resource.add(resource)
    messages.success(request, _("Compensation linked."))
    return redirect("resources:manager-show-resource", resource_slug=resource_slug)


@require_http_methods(["POST"])
@manager_required
def manager_unlink_compensation_view(
    request: HttpRequest, resource_slug: str, compensation_id: int
) -> HttpResponse:
    """Remove the link between a compensation and a resource (does not delete it)."""
    resource = get_object_or_404(Resource, slug=resource_slug)
    compensation = get_object_or_404(Compensation, pk=compensation_id)
    compensation.resource.remove(resource)
    messages.success(request, _("Compensation removed from this resource."))
    return redirect("resources:manager-show-resource", resource_slug=resource_slug)


@require_http_methods(["GET", "POST"])
@manager_required
def manager_create_compensation_view(
    request: HttpRequest, resource_slug: str
) -> HttpResponse:
    """Create a new compensation and link it to the resource."""
    resource = get_object_or_404(Resource, slug=resource_slug)

    if request.method == "POST":
        form = CompensationEditForm(request.POST)
        if form.is_valid():
            compensation = form.save()
            compensation.resource.add(resource)
            messages.success(request, _("Compensation created and linked."))
            return redirect(
                "resources:manager-show-resource", resource_slug=resource_slug
            )
    else:
        form = CompensationEditForm()

    return render(
        request,
        "resources/manager_edit_compensation.html",
        {
            "form": form,
            "resource": resource,
            "compensation": None,
            "affected_resources": [],
        },
    )


@require_http_methods(["POST"])
@manager_required
def manager_add_resource_image_view(
    request: HttpRequest, resource_slug: str
) -> HttpResponse:
    """Manager view to upload a new image for a resource."""
    resource = get_object_or_404(Resource, slug=resource_slug)
    form = ResourceImageForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save(commit=False)
        image.resource = resource
        image.save()
        messages.success(request, _("Image uploaded."))
    else:
        messages.error(request, _("Invalid image."))

    return redirect("resources:manager-show-resource", resource_slug=resource_slug)


@require_http_methods(["POST"])
@manager_required
def manager_delete_resource_image_view(
    request: HttpRequest, resource_slug: str, image_id: int
) -> HttpResponse:
    """Manager view to delete an image from a resource."""
    resource = get_object_or_404(Resource, slug=resource_slug)
    image = get_object_or_404(ResourceImage, pk=image_id, resource=resource)
    image.delete()
    messages.success(request, _("Image deleted."))
    return redirect("resources:manager-show-resource", resource_slug=resource_slug)
