from django.urls import resolve
from django.urls import reverse

from roomsharing.organizations.models import Organization


def test_show_organizations(organization: Organization):
    assert (
        reverse("organizations:show-organization", kwargs={"slug": organization.slug})
        == f"/organizations/{organization.slug}/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/").view_name
        == "organizations:show-organization"
    )


def test_list_organizations():
    assert reverse("organizations:list-organizations") == "/organizations/"
    assert resolve("/organizations/").view_name == "organizations:list-organizations"
