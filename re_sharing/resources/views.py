from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.services import filter_resources
from re_sharing.resources.services import planner
from re_sharing.resources.services import show_resource


@require_http_methods(["GET"])
def list_resources_view(request):
    persons_count = request.GET.get("persons_count")
    start_datetime = request.GET.get("start_datetime")
    resources = filter_resources(request.user, persons_count, start_datetime)
    context = {"resources": resources}
    if request.headers.get("HX-Request"):
        return render(request, "resources/partials/list_filter_resources.html", context)

    return render(request, "resources/list_resources.html", context)


@require_http_methods(["GET"])
def show_resource_view(request, resource_slug):
    date_string = request.GET.get("date")
    resource, timeslots, weekdays, dates, compensations = show_resource(
        resource_slug, date_string
    )

    context = {
        "resource": resource,
        "weekdays": weekdays,
        "timeslots": timeslots,
        "dates": dates,
        "compensations": compensations,
    }
    if request.headers.get("HX-Request"):
        return render(request, "resources/partials/weekly_bookings_table.html", context)

    return render(request, "resources/show_resource.html", context)


@require_http_methods(["GET"])
def planner_view(request):
    date_string = request.GET.get("date")
    selected_nb_of_days = int(request.GET.get("selected_nb_of_days", "7"))
    selected_resources_slugs = request.GET.getlist("resources")
    if request.user.is_authenticated:
        resources = request.user.get_resources()
    else:
        resources = Resource.objects.filter(is_private=False)
    if selected_resources_slugs:
        selected_resources = resources.filter(slug__in=selected_resources_slugs)
    else:
        selected_resources = resources

    grouped_resources = {}
    for access_type in resources.values_list("access__name", flat=True).distinct():
        grouped_resources[access_type] = resources.filter(access__name=access_type)

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
    }

    if request.headers.get("HX-Request"):
        return render(request, "resources/partials/multi_planner_table.html", context)
    return render(request, "resources/multi_planner.html", context)


@require_http_methods(["POST"])
def get_compensations(request):
    resource_id = request.POST.get("resource")
    if not resource_id:
        return render(
            request, "bookings/partials/compensations.html", {"compensations": []}
        )
    resource = get_object_or_404(Resource, id=resource_id)
    compensations = Compensation.objects.filter(resource=resource, is_active=True)
    return render(
        request,
        "bookings/partials/compensations.html",
        {"compensations": compensations},
    )
