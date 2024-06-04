from django.urls import path

from .views import list_organizations_view
from .views import show_organization_view

app_name = "organizations"
urlpatterns = [
    path("", list_organizations_view, name="list-organizations"),
    path("<slug:slug>/", show_organization_view, name="show-organization"),
]
