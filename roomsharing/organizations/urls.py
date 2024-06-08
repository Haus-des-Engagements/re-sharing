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
        "<slug:slug>/request-membership/",
        request_membership_view,
        name="request-membership",
    ),
    path(
        "<slug:slug>/confirm-membership/<slug:user>/",
        confirm_membership_view,
        name="confirm-membership",
    ),
    path(
        "<slug:slug>/cancel-membership/<slug:user>/",
        cancel_membership_view,
        name="cancel-membership",
    ),
    path(
        "<slug:slug>/delete-organization/",
        delete_organization_view,
        name="delete-organization",
    ),
    path("<slug:slug>/", show_organization_view, name="show-organization"),
]
