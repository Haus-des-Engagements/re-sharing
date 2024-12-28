from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import render

from .services import get_users_bookings_and_permissions


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
