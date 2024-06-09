from django.urls import resolve
from django.urls import reverse

from roomsharing.organizations.models import Organization
from roomsharing.users.models import User


def test_list_organizations():
    assert reverse("organizations:list-organizations") == "/organizations/"
    assert resolve("/organizations/").view_name == "organizations:list-organizations"


def test_filter_organizations():
    assert (
        reverse("organizations:filter-organizations")
        == "/organizations/filter-organizations/"
    )
    assert (
        resolve("/organizations/filter-organizations/").view_name
        == "organizations:filter-organizations"
    )


def test_request_membership(organization: Organization):
    assert (
        reverse(
            "organizations:request-membership",
            kwargs={"organization": organization.slug},
        )
        == f"/organizations/{organization.slug}/request-membership/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/request-membership/").view_name
        == "organizations:request-membership"
    )


def test_confirm_membership(organization: Organization, user: User):
    assert (
        reverse(
            "organizations:confirm-membership",
            kwargs={"organization": organization.slug, "user": user.slug},
        )
        == f"/organizations/{organization.slug}/confirm-membership/{user.slug}/"
    )
    assert (
        resolve(
            f"/organizations/{organization.slug}/confirm-membership/{user.slug}/"
        ).view_name
        == "organizations:confirm-membership"
    )


def test_cancel_membership(organization: Organization, user: User):
    assert (
        reverse(
            "organizations:cancel-membership",
            kwargs={"organization": organization.slug, "user": user.slug},
        )
        == f"/organizations/{organization.slug}/cancel-membership/{user.slug}/"
    )
    assert (
        resolve(
            f"/organizations/{organization.slug}/cancel-membership/{user.slug}/"
        ).view_name
        == "organizations:cancel-membership"
    )


def test_delete_organization(organization: Organization):
    assert (
        reverse(
            "organizations:delete-organization",
            kwargs={"organization": organization.slug},
        )
        == f"/organizations/{organization.slug}/delete-organization/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/delete-organization/").view_name
        == "organizations:delete-organization"
    )


def test_show_organization(organization: Organization):
    assert (
        reverse(
            "organizations:show-organization",
            kwargs={"organization": organization.slug},
        )
        == f"/organizations/{organization.slug}/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/").view_name
        == "organizations:show-organization"
    )
