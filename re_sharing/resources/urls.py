from django.urls import include
from django.urls import path

from .views import AccessCodeView
from .views import ResourceIcalFeed
from .views import get_compensations
from .views import list_resources_view
from .views import manager_add_resource_image_view
from .views import manager_create_compensation_view
from .views import manager_delete_resource_image_view
from .views import manager_edit_compensation_view
from .views import manager_edit_resource_view
from .views import manager_link_compensation_view
from .views import manager_list_resources_view
from .views import manager_show_resource_view
from .views import manager_unlink_compensation_view
from .views import planner_view
from .views import show_resource_view

app_name = "resources"
urlpatterns = [
    path("", list_resources_view, name="list-resources"),
    path(
        "get-compensations/<int:selected_compensation>",
        get_compensations,
        name="get-compensations",
    ),
    path("planner/", planner_view, name="planner"),
    path("access-codes/", include(AccessCodeView.get_urls())),
    # Manager resource views
    path("manager/", manager_list_resources_view, name="manager-list-resources"),
    path(
        "manager/<slug:resource_slug>/",
        manager_show_resource_view,
        name="manager-show-resource",
    ),
    path(
        "manager/<slug:resource_slug>/edit/",
        manager_edit_resource_view,
        name="manager-edit-resource",
    ),
    path(
        "manager/compensations/<int:compensation_id>/edit/",
        manager_edit_compensation_view,
        name="manager-edit-compensation",
    ),
    path(
        "manager/<slug:resource_slug>/compensations/link/",
        manager_link_compensation_view,
        name="manager-link-compensation",
    ),
    path(
        "manager/<slug:resource_slug>/compensations/<int:compensation_id>/unlink/",
        manager_unlink_compensation_view,
        name="manager-unlink-compensation",
    ),
    path(
        "manager/<slug:resource_slug>/compensations/new/",
        manager_create_compensation_view,
        name="manager-create-compensation",
    ),
    path(
        "manager/<slug:resource_slug>/images/add/",
        manager_add_resource_image_view,
        name="manager-add-resource-image",
    ),
    path(
        "manager/<slug:resource_slug>/images/<int:image_id>/delete/",
        manager_delete_resource_image_view,
        name="manager-delete-resource-image",
    ),
    path(
        "<slug:resource_slug>/daily-calendar.ics",
        ResourceIcalFeed(),
        name="daily-calendar",
    ),
    path("<slug:resource_slug>/", show_resource_view, name="show-resource"),
]
