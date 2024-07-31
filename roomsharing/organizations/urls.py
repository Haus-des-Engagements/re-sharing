from django.urls import path

from .views import cancel_bookingpermission_view
from .views import confirm_bookingpermission_view
from .views import delete_organization_view
from .views import demote_to_booker_view
from .views import list_organizations_view
from .views import promote_to_admin_view
from .views import request_bookingpermission_view
from .views import show_organization_view

app_name = "organizations"
urlpatterns = [
    path("", list_organizations_view, name="list-organizations"),
    path(
        "<slug:organization>/request-bookingpermission/",
        request_bookingpermission_view,
        name="request-bookingpermission",
    ),
    path(
        "<slug:organization>/confirm-bookingpermission/<slug:user>/",
        confirm_bookingpermission_view,
        name="confirm-bookingpermission",
    ),
    path(
        "<slug:organization>/cancel-bookingpermission/<slug:user>/",
        cancel_bookingpermission_view,
        name="cancel-bookingpermission",
    ),
    path(
        "<slug:organization>/promote-to-admin/<slug:user>/",
        promote_to_admin_view,
        name="promote-to-admin",
    ),
    path(
        "<slug:organization>/demote-to-booker/<slug:user>/",
        demote_to_booker_view,
        name="demote-to-booker",
    ),
    path(
        "<slug:organization>/delete-organization/",
        delete_organization_view,
        name="delete-organization",
    ),
    path("<slug:organization>/", show_organization_view, name="show-organization"),
]
