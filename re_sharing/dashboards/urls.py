from django.urls import path

from re_sharing.dashboards.views import reporting_view
from re_sharing.dashboards.views import users_bookings_and_permissions_dashboard_view

app_name = "dashboards"
urlpatterns = [
    path(
        "",
        users_bookings_and_permissions_dashboard_view,
        name="users_bookings_and_permissions",
    ),
    path("reports/", reporting_view, name="reports"),
]
