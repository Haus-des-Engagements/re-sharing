from django.urls import path

from .views import add_user_view
from .views import cancel_bookingpermission_view
from .views import confirm_bookingpermission_view
from .views import create_organization_view
from .views import delete_organization_view
from .views import demote_to_booker_view
from .views import list_organizations_view
from .views import manager_cancel_organization_view
from .views import manager_confirm_organization_view
from .views import manager_list_organizations_view
from .views import promote_to_admin_view
from .views import request_bookingpermission_view
from .views import show_organization_view
from .views import update_organization_view

app_name = "organizations"
urlpatterns = [
    path("", list_organizations_view, name="list-organizations"),  # GET organizations
    path(
        "manage-organizations/",
        manager_list_organizations_view,
        name="manager-list-organizations",
    ),
    path(
        "manage-organizations/<slug:organization_slug>/cancel-organization/",
        manager_cancel_organization_view,
        name="manager-cancel-organization",
    ),
    path(
        "manage-organizations/<slug:organization_slug>/confirm-organization/",
        manager_confirm_organization_view,
        name="manager-confirm-organization",
    ),
    path(
        "<slug:organization>/edit/",
        update_organization_view,
        name="update-organization",
    ),
    path("new/", create_organization_view, name="create-organization"),
    path(
        "<slug:organization>/request-bookingpermission/",
        request_bookingpermission_view,
        name="request-bookingpermission",
    ),  # POST bookingpermission
    path(
        "<slug:organization>/add-user/",
        add_user_view,
        name="add-user",
    ),
    path(
        "<slug:organization>/confirm-bookingpermission/<slug:user>/",
        confirm_bookingpermission_view,
        name="confirm-bookingpermission",
    ),  # PUT bookingpermission
    path(
        "<slug:organization>/cancel-bookingpermission/<slug:user>/",
        cancel_bookingpermission_view,
        name="cancel-bookingpermission",
    ),  # DELETE bookingspermission
    path(
        "<slug:organization>/promote-to-admin/<slug:user>/",
        promote_to_admin_view,
        name="promote-to-admin",
    ),  # PUT bookingpermission
    path(
        "<slug:organization>/demote-to-booker/<slug:user>/",
        demote_to_booker_view,
        name="demote-to-booker",
    ),  # PUT bookingpermission
    path(
        "<slug:organization>/delete-organization/",
        delete_organization_view,
        name="delete-organization",
    ),  # DELETE organization
    path(
        "<slug:organization>/", show_organization_view, name="show-organization"
    ),  # GET organization
]
