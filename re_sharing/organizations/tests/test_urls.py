from django.urls import resolve
from django.urls import reverse

from re_sharing.organizations.models import Organization
from re_sharing.users.models import User


def test_list_organizations():
    assert reverse("organizations:list-organizations") == "/organizations/"
    assert resolve("/organizations/").view_name == "organizations:list-organizations"


def test_request_bookingpermission(organization: Organization):
    assert (
        reverse(
            "organizations:request-bookingpermission",
            kwargs={"organization": organization.slug},
        )
        == f"/organizations/{organization.slug}/request-bookingpermission/"
    )
    assert (
        resolve(
            f"/organizations/{organization.slug}/request-bookingpermission/"
        ).view_name
        == "organizations:request-bookingpermission"
    )


def test_confirm_bookingpermission(organization: Organization, user: User):
    assert (
        reverse(
            "organizations:confirm-bookingpermission",
            kwargs={"organization": organization.slug, "user": user.slug},
        )
        == f"/organizations/{organization.slug}/confirm-bookingpermission/{user.slug}/"
    )
    assert (
        resolve(
            f"/organizations/{organization.slug}/confirm-bookingpermission/{user.slug}/"
        ).view_name
        == "organizations:confirm-bookingpermission"
    )


def test_cancel_bookingpermission(organization: Organization, user: User):
    assert (
        reverse(
            "organizations:cancel-bookingpermission",
            kwargs={"organization": organization.slug, "user": user.slug},
        )
        == f"/organizations/{organization.slug}/cancel-bookingpermission/{user.slug}/"
    )
    assert (
        resolve(
            f"/organizations/{organization.slug}/cancel-bookingpermission/{user.slug}/"
        ).view_name
        == "organizations:cancel-bookingpermission"
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


def test_manager_list_organizations_view():
    assert (
        reverse("organizations:manager-list-organizations")
        == "/organizations/manage-organizations/"
    )
    assert (
        resolve("/organizations/manage-organizations/").view_name
        == "organizations:manager-list-organizations"
    )


def test_manager_cancel_organization(organization: Organization):
    assert (
        reverse(
            "organizations:manager-cancel-organization",
            kwargs={"organization_slug": organization.slug},
        )
        == f"/organizations/manage-organizations/{organization.slug}/cancel"
        f"-organization/"
    )


def test_manager_confirm_organization(organization: Organization):
    assert (
        reverse(
            "organizations:manager-confirm-organization",
            kwargs={"organization_slug": organization.slug},
        )
        == f"/organizations/manage-organizations/{organization.slug}/confirm"
        f"-organization/"
    )
