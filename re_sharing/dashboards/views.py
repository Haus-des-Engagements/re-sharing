from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Sum
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import render

from re_sharing.bookings.models import Booking
from re_sharing.dashboards.services import get_users_bookings_and_permissions


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


@staff_member_required
def reporting_view(request: HttpRequest) -> HttpResponse:
    """
    View that renders a reporting dashboard.
    """
    bookings = (
        Booking.objects.filter(start_date__year=2025)
        .values("resource__name", "start_date__month")
        .annotate(bookings_count=Count("id"), amount=Sum("total_amount"))
        .order_by("resource__name", "start_date__month")
    )
    monthly_totals = (
        Booking.objects.filter(start_date__year=2025)
        .values("start_date__month")
        .annotate(bookings_count=Count("id"), amount=Sum("total_amount"))
        .order_by("start_date__month")
    )
    yearly_totals = Booking.objects.filter(start_date__year=2025).aggregate(
        bookings_count=Count("id"), amount=Sum("total_amount")
    )

    # Render to the template
    return render(
        request,
        "dashboards/reporting.html",
        context={
            "bookings": bookings,
            "months": range(1, 13),
            "monthly_totals": monthly_totals,
            "yearly_totals": yearly_totals,
        },
    )
