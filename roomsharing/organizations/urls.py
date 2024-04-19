from django.urls import path

from .views import my_organization_list
from .views import organization_detail
from .views import organization_list

app_name = "organizations"
urlpatterns = [
    path("", my_organization_list, name="my_organization_list"),
    path("all/", organization_list, name="organization_list"),
    path("<slug:organization_slug>/", organization_detail, name="organization_detail"),
]
