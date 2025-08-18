from django.urls import resolve
from django.urls import reverse

from re_sharing.organizations.models import Organization
from re_sharing.users.models import User


def test_list_organizations():
    assert reverse("organizations:list-organizations") == "/organizations/"
    assert resolve("/organizations/").view_name == "organizations:list-organizations"


def test_organization_permissions(organization: Organization):
    """Test consolidated permission creation endpoint"""
    assert (
        reverse(
            "organizations:organization-permissions",
            kwargs={"organization": organization.slug},
        )
        == f"/organizations/{organization.slug}/permissions/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/permissions/").view_name
        == "organizations:organization-permissions"
    )


def test_organization_permissions_manage(organization: Organization, user: User):
    """Test consolidated permission management endpoint"""
    assert (
        reverse(
            "organizations:organization-permissions-manage",
            kwargs={"organization": organization.slug, "user": user.slug},
        )
        == f"/organizations/{organization.slug}/permissions/{user.slug}/"
    )
    assert (
        resolve(
            f"/organizations/{organization.slug}/permissions/{user.slug}/"
        ).view_name
        == "organizations:organization-permissions-manage"
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


def test_show_organization_messages(organization: Organization):
    assert (
        reverse(
            "organizations:show-organization-messages",
            kwargs={"organization": organization.slug},
        )
        == f"/organizations/{organization.slug}/messages/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/messages/").view_name
        == "organizations:show-organization-messages"
    )


def test_create_organizationmessage(organization: Organization):
    assert (
        reverse(
            "organizations:create-organizationmessage",
            kwargs={"slug": organization.slug},
        )
        == f"/organizations/{organization.slug}/create-message/"
    )
    assert (
        resolve(f"/organizations/{organization.slug}/create-message/").view_name
        == "organizations:create-organizationmessage"
    )
