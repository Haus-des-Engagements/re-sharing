from django.urls import path

from .views import cancel_membership_view
from .views import confirm_membership_view
from .views import delete_organization_view
from .views import filter_organizations_view
from .views import list_organizations_view
from .views import request_membership_view
from .views import show_organization_view

app_name = "organizations"
urlpatterns = [
    path("", list_organizations_view, name="list-organizations"),
    path(
        "filter-organizations/", filter_organizations_view, name="filter-organizations"
    ),
    path(
        "<slug:organization>/request-membership/",
        request_membership_view,
        name="request-membership",
    ),
    path(
        "<slug:organization>/confirm-membership/<slug:user>/",
        confirm_membership_view,
        name="confirm-membership",
    ),
    path(
        "<slug:organization>/cancel-membership/<slug:user>/",
        cancel_membership_view,
        name="cancel-membership",
    ),
    path(
        "<slug:organization>/delete-organization/",
        delete_organization_view,
        name="delete-organization",
    ),
    path("<slug:organization>/", show_organization_view, name="show-organization"),
]
