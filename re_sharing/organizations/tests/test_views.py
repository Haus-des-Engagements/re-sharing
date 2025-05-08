from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from config.settings.base import ADMIN_URL
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.models import OrganizationMessage
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationMessageFactory
from re_sharing.organizations.views import list_organizations_view
from re_sharing.organizations.views import manager_list_organizations_view
from re_sharing.users.tests.factories import UserFactory


class TestListOrganizationView(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.organization1 = OrganizationFactory()
        self.organization2 = OrganizationFactory()
        self.list_organizations_url = reverse("organizations:list-organizations")

    def test_list_organizations(self):
        response = self.client.get(self.list_organizations_url)
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "organizations/list_organizations.html")
        organizations = response.context.get("organizations")

        assert set(organizations) == {self.organization1, self.organization2}

    @pytest.mark.django_db()
    def test_list_organizations_view_hx_request(self):
        request = self.rf.get(
            reverse("organizations:list-organizations"), HTTP_HX_REQUEST="true"
        )
        response = list_organizations_view(request)
        assert response.status_code == HTTPStatus.OK


class TestShowOrganizationView(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.organization = OrganizationFactory()
        self.show_organization_url = reverse(
            "organizations:show-organization",
            kwargs={"organization": self.organization.slug},
        )

    def test_show_organization(self):
        response = self.client.get(self.show_organization_url)
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "organizations/show_organization.html")


class TestRequestBookingpermissionView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.organization = OrganizationFactory()
        self.request_bookingpermission_url = reverse(
            "organizations:request-bookingpermission",
            kwargs={"organization": self.organization.slug},
        )

    def test_request_pending(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.PENDING,
        )

        response = self.client.get(self.request_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "You are already requested to become a member. Please wait patiently.",
        )

    def test_already_confirmed(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )

        response = self.client.get(self.request_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "You are already member of this organization.")

    def test_rejected(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.REJECTED,
        )

        response = self.client.get(self.request_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response, "You have already been rejected by this organization."
        )

    def test_new_request(self):
        response = self.client.get(self.request_bookingpermission_url)
        bookingpermission = (
            BookingPermission.objects.filter(organization=self.organization)
            .filter(user=self.user)
            .first()
        )
        assert bookingpermission
        assert bookingpermission.organization == self.organization
        assert bookingpermission.user == self.user
        assert bookingpermission.role == BookingPermission.Role.BOOKER
        assert bookingpermission.status == BookingPermission.Status.PENDING

        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Successfully requested. "
            "You will be notified when your request is approved or denied.",
        )


class ConfirmBookingpermissionView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.confirm_bookingpermission_url = reverse(
            "organizations:confirm-bookingpermission",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_confirm_already_confirmed_bookingpermission_by_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.confirm_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Booking permission has already been confirmed.")

    def test_confirm_new_bookingpermission_by_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.PENDING,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.confirm_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Booking permission has been confirmed.")

    def test_confirm_new_bookingpermission_by_non_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.PENDING,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.confirm_bookingpermission_url)
        self.assertContains(
            response,
            "You are not allowed to confirm this booking permission.",
            status_code=401,
        )


class CancelBookingpermissionView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.cancel_bookingpermission_url = reverse(
            "organizations:cancel-bookingpermission",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_cancel_existing_bookingpermission_by_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )

        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.cancel_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Booking permission has been cancelled.",
        )
        assert (
            not BookingPermission.objects.filter(organization=self.organization)
            .filter(user__slug=self.user)
            .exists()
        )

    def test_cancel_not_existing_bookingpermission_by_admin(self):
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.cancel_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Booking permission does not exist.",
        )
        assert (
            not BookingPermission.objects.filter(organization=self.organization)
            .filter(user__slug=self.user)
            .exists()
        )

    def test_cancel_bookingpermission_by_non_admin(self):
        orga_booker = UserFactory()
        BookingPermissionFactory(
            user=orga_booker,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(orga_booker)

        response = self.client.get(self.cancel_bookingpermission_url)
        self.assertContains(
            response,
            "You are not allowed to cancel this booking permission.",
            status_code=401,
        )

    def test_cancel_bookingpermission_by_user_itself(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.cancel_bookingpermission_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Booking permission has been cancelled.",
        )
        assert (
            not BookingPermission.objects.filter(organization=self.organization)
            .filter(user__slug=self.user)
            .exists()
        )


class PromoteToAdminView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.promote_to_admin_url = reverse(
            "organizations:promote-to-admin",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_promote_to_admin_membership_by_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.promote_to_admin_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "User has been promoted to admin.")
        assert (
            BookingPermission.objects.filter(
                organization=self.organization, user=self.user
            )
            .first()
            .role
            == BookingPermission.Role.ADMIN
        )

    def test_promote_to_admin_by_non_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.promote_to_admin_url)
        self.assertContains(
            response,
            "You are not allowed to promote.",
            status_code=HTTPStatus.UNAUTHORIZED,
        )


class DemoteToBookerView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.demote_to_booker_url = reverse(
            "organizations:demote-to-booker",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_demote_to_booker_by_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.demote_to_booker_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "User has been demoted to booker.")
        assert (
            BookingPermission.objects.filter(
                organization=self.organization, user=self.user
            )
            .first()
            .role
            == BookingPermission.Role.BOOKER
        )

    def test_demote_to_admin_by_non_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.demote_to_booker_url)
        self.assertContains(
            response,
            "You are not allowed to demote.",
            status_code=HTTPStatus.UNAUTHORIZED,
        )


class DeleteOrganizationView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.delete_organization_url = reverse(
            "organizations:delete-organization",
            kwargs={"organization": self.organization.slug},
        )

    def test_delete_ogranization_by_admin(self):
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

        self.client.force_login(self.orga_admin)

        response = self.client.get(self.delete_organization_url)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("organizations:list-organizations")
        with pytest.raises(Organization.DoesNotExist):
            self.organization.refresh_from_db()

    def test_delete_organization_by_non_admin(self):
        BookingPermissionFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.delete_organization_url)
        self.assertContains(
            response,
            "You are not allowed to delete this organization.",
            status_code=HTTPStatus.UNAUTHORIZED,
        )


class TestManagerOrganizationsView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory(is_staff=True)

    def test_authenticated(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse("organizations:manager-list-organizations"))
        assert response.status_code == HTTPStatus.OK

    def test_not_authenticated(self):
        request = self.factory.get("/organizations/manage-organizations/")
        request.user = AnonymousUser()
        response = manager_list_organizations_view(request)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/{ADMIN_URL}login/?next=/organizations/manage-organizations/"
        )


class TestManagerActionsOrganizationView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.user = UserFactory(is_staff=False)
        self.organization = OrganizationFactory()
        self.cancel_organization_url = reverse(
            "organizations:manager-cancel-organization",
            kwargs={"organization_slug": self.organization.slug},
        )
        self.confirm_organization_url = reverse(
            "organizations:manager-confirm-organization",
            kwargs={"organization_slug": self.organization.slug},
        )

    @patch(
        "re_sharing.organizations.models.Organization.is_cancelable", return_value=True
    )
    def test_cancel_by_staff(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.staff_user)

        response = client.patch(self.cancel_organization_url)
        assert response.status_code == HTTPStatus.OK

    @patch(
        "re_sharing.organizations.models.Organization.is_cancelable", return_value=True
    )
    def test_cancel_by_non_staff(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.cancel_organization_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/{ADMIN_URL}login/?next=/organizations/manage-organizations/"
            f"{self.organization.slug}/cancel-organization/"
        )

    @patch(
        "re_sharing.organizations.models.Organization.is_confirmable",
        return_value=True,
    )
    def test_confirm_by_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.staff_user)

        response = client.patch(self.confirm_organization_url)
        assert response.status_code == HTTPStatus.OK

    @patch(
        "re_sharing.organizations.models.Organization.is_confirmable",
        return_value=True,
    )
    def test_confirm_by_non_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.confirm_organization_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/{ADMIN_URL}login/?next=/organizations/manage-organizations/"
            f"{self.organization.slug}/confirm-organization/"
        )


class TestShowOrganizationMessagesView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.organization_message = OrganizationMessageFactory(
            organization=self.organization, user=self.user
        )
        self.show_organization_messages_url = reverse(
            "organizations:show-organization-messages",
            kwargs={"organization": self.organization.slug},
        )

    def test_show_organization_messages_authenticated_with_permission(self):
        # Create booking permission for the user
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.show_organization_messages_url)
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(
            response, "organizations/show_organization_messages.html"
        )

        # Check that the organization message is in the context
        organization_messages = response.context.get("organization_messages")
        assert self.organization_message in organization_messages

    def test_show_organization_messages_authenticated_without_permission(self):
        # User without permission should get a 403 Forbidden
        other_user = UserFactory()
        self.client.force_login(other_user)

        response = self.client.get(self.show_organization_messages_url)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_show_organization_messages_unauthenticated(self):
        # Unauthenticated user should be redirected to login
        response = self.client.get(self.show_organization_messages_url)
        assert response.status_code == HTTPStatus.FOUND  # 302 redirect
        assert "/accounts/login/" in response.url

    def test_show_organization_messages_staff_user(self):
        # Staff user should be able to see messages even without permission
        staff_user = UserFactory(is_staff=True)
        self.client.force_login(staff_user)

        response = self.client.get(self.show_organization_messages_url)
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(
            response, "organizations/show_organization_messages.html"
        )


class TestCreateOrganizationMessageView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.create_organizationmessage_url = reverse(
            "organizations:create-organizationmessage",
            kwargs={"slug": self.organization.slug},
        )

    def test_create_organization_message_authenticated_with_permission(self):
        self.client.force_login(self.user)

        # Count messages before
        message_count_before = OrganizationMessage.objects.count()

        # Post a new message
        response = self.client.post(
            self.create_organizationmessage_url,
            {"text": "Test message content"},
        )

        # Check response
        assert response.status_code == HTTPStatus.OK

        # Check that a new message was created
        assert OrganizationMessage.objects.count() == message_count_before + 1

        # Check the message content
        new_message = OrganizationMessage.objects.latest("created")
        assert new_message.text == "Test message content"
        assert new_message.user == self.user
        assert new_message.organization == self.organization

    def test_create_organization_message_authenticated_without_permission(self):
        # User without permission should get a 403 Forbidden
        other_user = UserFactory()
        self.client.force_login(other_user)

        response = self.client.post(
            self.create_organizationmessage_url,
            {"text": "Test message content"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_create_organization_message_unauthenticated(self):
        # Unauthenticated user should be redirected to login
        response = self.client.post(
            self.create_organizationmessage_url,
            {"text": "Test message content"},
        )
        assert response.status_code == HTTPStatus.FOUND  # 302 redirect
        assert "/accounts/login/" in response.url
