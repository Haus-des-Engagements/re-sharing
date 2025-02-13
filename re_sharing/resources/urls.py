from django.urls import path

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
    path("<slug:resource_slug>/", show_resource_view, name="show-resource"),
]
