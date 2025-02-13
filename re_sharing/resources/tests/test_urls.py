from django.urls import resolve
from django.urls import reverse

from re_sharing.resources.models import Resource


def test_show_resource(resource: Resource):
    assert (
        reverse("resources:show-resource", kwargs={"resource_slug": resource.slug})
        == f"/resources/{resource.slug}/"
    )
    assert (
        resolve(f"/resources/{resource.slug}/").view_name == "resources:show-resource"
    )


def test_list_resources():
    assert reverse("resources:list-resources") == "/resources/"
    assert resolve("/resources/").view_name == "resources:list-resources"


def test_resource_planner():
    assert reverse("resources:planner") == "/resources/planner/"
    assert resolve("/resources/planner/").view_name == "resources:planner"


def test_get_compensations():
    assert (
        reverse("resources:get-compensations", kwargs={"selected_compensation": 1})
        == "/resources/get-compensations/1"
    )
    assert (
        resolve("/resources/get-compensations/1").view_name
        == "resources:get-compensations"
    )
