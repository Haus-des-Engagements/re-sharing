from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

import django_filters
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sites.models import Site
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ical.views import ICalFeed
from neapolitan.views import CRUDView

from re_sharing.bookings.models import Booking
from re_sharing.organizations.models import Organization
from re_sharing.providers.decorators import ManagerRequiredMixin
from re_sharing.resources.models import Access
from re_sharing.resources.models import AccessCode
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceRestriction
from re_sharing.resources.services import filter_resources
from re_sharing.resources.services import get_user_accessible_locations
from re_sharing.resources.services import planner
from re_sharing.resources.services import show_resource
from re_sharing.utils.models import BookingStatus


class AccessCodeFilterSet(django_filters.FilterSet):
    """Custom filterset for AccessCode to limit Access choices dynamically."""

    access = django_filters.ModelChoiceFilter(queryset=Access.objects.none())

    class Meta:
        model = AccessCode
        fields = ["access", "code", "validity_start", "organization"]

    def __init__(self, *args, **kwargs):
        # Extract the request from kwargs to get the user
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # If we have a request and the user is a manager, limit Access choices
        if request and hasattr(request, "user") and request.user.is_manager():
            manager = request.user.get_manager()
            self.filters["access"].queryset = manager.get_accessible_accesses()


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


class AccessCodeView(LoginRequiredMixin, ManagerRequiredMixin, CRUDView):
    model = AccessCode
    fields = ["access", "code", "validity_start", "organization"]
    lookup_field = "uuid"
    path_converter = "uuid"
    filterset_class = AccessCodeFilterSet

    def get_queryset(self):
        """
        Filter AccessCodes to only show codes for resources the manager has access
        to.
        """
        manager = self.request.user.get_manager()
        return manager.get_accessible_access_codes()

    def get_filterset_kwargs(self, filterset_class):
        """
        Pass the request to the filterset so it can limit Access choices.
        """
        kwargs = super().get_filterset_kwargs(filterset_class)
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        return reverse("resources:accesscode-list")


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
