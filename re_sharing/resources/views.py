from datetime import date
from datetime import time

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from re_sharing.organizations.models import Organization
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceRestriction
from re_sharing.resources.services import filter_resources
from re_sharing.resources.services import get_user_accessible_locations
from re_sharing.resources.services import planner
from re_sharing.resources.services import show_resource


@require_http_methods(["GET"])
def list_resources_view(request):
    persons_count = request.GET.get("persons_count")
    start_datetime = request.GET.get("start_datetime")
    location_slug = request.GET.get("location")
    resources = filter_resources(
        request.user, persons_count, start_datetime, location_slug
    )
    locations = get_user_accessible_locations(request.user)
    context = {
        "resources": resources,
        "locations": locations,
    }
    if request.headers.get("HX-Request"):
        return render(request, "resources/partials/list_filter_resources.html", context)

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
        return render(request, "resources/partials/weekly_bookings_table.html", context)

    return render(request, "resources/show_resource.html", context)


@require_http_methods(["GET"])
def planner_view(request):
    date_string = request.GET.get("date")
    selected_nb_of_days = int(request.GET.get("selected_nb_of_days", "7"))
    selected_resources_slugs = request.GET.getlist("resources")
    location_slug = request.GET.get("location")

    if request.user.is_authenticated:
        resources = request.user.get_resources()
    else:
        resources = Resource.objects.filter(is_private=False)

    # Filter resources by location if specified
    if location_slug:
        resources = resources.filter(location__slug=location_slug)

    if selected_resources_slugs:
        selected_resources = resources.filter(slug__in=selected_resources_slugs)
    else:
        selected_resources = resources.filter(type=Resource.ResourceTypeChoices.ROOM)

    grouped_resources = {}
    for access_type in resources.values_list("access__name", flat=True).distinct():
        grouped_resources[access_type] = resources.filter(access__name=access_type)

    # Get locations that the user has access to
    locations = get_user_accessible_locations(request.user)

    resource, timeslots, weekdays, dates, planner_data = planner(
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
        return render(request, "resources/partials/selection_and_table.html", context)
    if (
        request.headers.get("HX-Request")
        and request.headers.get("partial") == "planner-table"
    ):
        return render(request, "resources/partials/multi_planner_table.html", context)
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
    from datetime import datetime

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
            Compensation, id=selected_compensation, resource=resource
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
