from django.urls import include
from django.urls import path

from .views import AccessCodeView
from .views import ResourceIcalFeed
from .views import get_compensations
from .views import list_resources_view
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
    path(
        "<slug:resource_slug>/daily-calendar.ics",
        ResourceIcalFeed(),
        name="daily-calendar",
    ),
    path("<slug:resource_slug>/", show_resource_view, name="show-resource"),
]
