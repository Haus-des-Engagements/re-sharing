from datetime import datetime
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.dashboards.services import get_users_bookings_and_permissions
from re_sharing.organizations.models import Organization
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.utils.models import BookingStatus


@login_required
def users_bookings_and_permissions_dashboard_view(request: HttpRequest) -> HttpResponse:
    """
    View that renders a dashboard with the bookings and booking permissions of
    all the organizations the user belongs to.
    """
    bookings, booking_permissions = get_users_bookings_and_permissions(
        user=request.user
    )

    return render(
        request,
        "dashboards/users_bookings_and_permissions.html",
        {
            "bookings": bookings,
            "booking_permissions": booking_permissions,
            "user": request.user,
        },
    )


def home_view(request: HttpRequest) -> HttpResponse:
    """
    View that renders the home page with statistics.
    """
    # Cache key for the statistics
    cache_key = "home_statistics"

    # Try to get statistics from cache
    statistics = cache.get(cache_key)

    # If not in cache, calculate and cache for 24 hours
    if statistics is None:
        yesterday = timezone.now().date() - timedelta(days=1)
        current_year_start = datetime(
            yesterday.year, 1, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone()
        )

        # Get non-parking resources
        non_parking_resources = Resource.objects.exclude(
            type=Resource.ResourceTypeChoices.PARKING_LOT
        )

        # Get IDs of non-parking resources
        non_parking_resource_ids = non_parking_resources.values_list("id", flat=True)

        # Total confirmed bookings this year until yesterday
        confirmed_bookings = Booking.objects.filter(
            status=2,  # CONFIRMED
            start_date__gte=current_year_start,
            start_date__lte=yesterday,
            resource_id__in=non_parking_resource_ids,
        ).count()

        bookings_with_comp1 = Booking.objects.filter(
            compensation_id=1,
            start_date__gte=current_year_start,
            start_date__lte=yesterday,
            status=2,
        )

        total_hours = 0
        free_bookings_value = 0
        for booking in bookings_with_comp1:
            duration = (
                booking.timespan.upper - booking.timespan.lower
            ).total_seconds() / 3600
            total_hours += duration

            most_expensive_comp = (
                Compensation.objects.filter(
                    resource=booking.resource, hourly_rate__isnull=False
                )
                .order_by("-hourly_rate")
                .first()
            )

            if most_expensive_comp:
                free_bookings_value += duration * most_expensive_comp.hourly_rate

        # Caluclate the value of the reduced compensation (id=14 and id=6)
        # for the event room
        total_amount_reduced_bookings = Booking.objects.filter(
            compensation_id__in=[6, 14],
            start_date__gte=current_year_start,
            start_date__lte=yesterday,
            resource_id__in=non_parking_resource_ids,
            status=2,
        ).aggregate(total_amount=Sum("total_amount"))

        total_amount_reduced_bookings = (
            total_amount_reduced_bookings["total_amount"] or 0 * 2
        )

        free_total = free_bookings_value + int(total_amount_reduced_bookings)

        # Number of registered organizations
        registered_organizations = Organization.objects.filter(
            status=Organization.Status.CONFIRMED
        ).count()

        # Create statistics dictionary
        statistics = {
            "confirmed_bookings": confirmed_bookings,
            "total_hours_comp1": round(total_hours),
            "registered_organizations": registered_organizations,
            "free_bookings_value": round(free_total),
        }

        # Cache for 24 hours
        cache.set(cache_key, statistics, 60 * 60 * 24)

    # Render the home template with statistics
    return render(
        request,
        "pages/home.html",
        context=statistics,
    )


@staff_member_required
def reporting_view(request: HttpRequest) -> HttpResponse:
    """
    View that renders a reporting dashboard.
    """
    bookings_by_resource = (
        Booking.objects.filter(start_date__year=2025, status=BookingStatus.CONFIRMED)
        .values("resource__name", "start_date__month")
        .annotate(bookings_count=Count("id"), amount=Sum("total_amount"))
        .order_by("resource__name", "start_date__month")
    )

    months = list(range(1, 13))
    resources = Resource.objects.all().order_by("location__id")

    bookings_by_resource = []
    for resource in resources:
        for month in months:
            booking_data = Booking.objects.filter(
                start_date__year=2025,
                start_date__month=month,
                resource=resource,
                status=BookingStatus.CONFIRMED,
            ).aggregate(
                bookings_count=Count("id"),
                amount=Sum("total_amount"),
                not_invoiced_amount=Sum("total_amount", filter=Q(invoice_number="")),
            )

            bookings_by_resource.append(
                {
                    "resource__name": resource.name,
                    "start_date__month": month,
                    "bookings_count": booking_data["bookings_count"] or "",
                    "amount": booking_data["amount"] or "",
                    "not_invoiced_amount": booking_data["not_invoiced_amount"] or "",
                }
            )

    monthly_totals = (
        Booking.objects.filter(start_date__year=2025, status=BookingStatus.CONFIRMED)
        .values("start_date__month")
        .annotate(
            bookings_count=Count("id"),
            amount=Sum("total_amount"),
            not_invoiced_amount=Sum("total_amount", filter=Q(invoice_number="")),
        )
        .order_by("start_date__month")
    )
    yearly_totals = Booking.objects.filter(
        start_date__year=2025, status=BookingStatus.CONFIRMED
    ).aggregate(bookings_count=Count("id"), amount=Sum("total_amount"))
    realized_yearly_totals = Booking.objects.filter(
        start_date__year=2025,
        start_date__lt=timezone.now(),
        status=BookingStatus.CONFIRMED,
    ).aggregate(bookings_count=Count("id"), amount=Sum("total_amount"))

    not_yet_invoiced = Booking.objects.filter(
        start_date__year=2025,
        status=BookingStatus.CONFIRMED,
        invoice_number="",
        total_amount__gt=0,
    ).aggregate(bookings_count=Count("id"), amount=Sum("total_amount"))

    # Render to the template
    return render(
        request,
        "dashboards/reporting.html",
        context={
            "bookings_by_resource": bookings_by_resource,
            "months": range(1, 13),
            "monthly_totals": monthly_totals,
            "yearly_totals": yearly_totals,
            "realized_yearly_totals": realized_yearly_totals,
            "not_yet_invoiced": not_yet_invoiced,
        },
    )
