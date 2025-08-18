from http import HTTPStatus

import pytest
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.models import OrganizationMessage
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationMessageFactory
from re_sharing.organizations.views import list_organizations_view
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


class TestDeleteOrganizationView(TestCase):
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


class TestOrganizationPermissionView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.admin_user = UserFactory()
        self.organization = OrganizationFactory()
        self.permission_url = reverse(
            "organizations:organization-permissions",
            kwargs={"organization": self.organization.slug},
        )

        # Create admin permission for admin_user
        BookingPermissionFactory(
            user=self.admin_user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

    def test_request_permission_new_user(self):
        self.client.force_login(self.user)

        response = self.client.post(self.permission_url, {"action": "request"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Successfully requested")

        # Check that permission was created
        permission = BookingPermission.objects.filter(
            user=self.user, organization=self.organization
        ).first()
        assert permission
        assert permission.status == BookingPermission.Status.PENDING
        assert permission.role == BookingPermission.Role.BOOKER

    def test_request_permission_already_pending(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.PENDING,
        )
        self.client.force_login(self.user)

        response = self.client.post(self.permission_url, {"action": "request"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "already requested")

    def test_request_permission_already_confirmed(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.post(self.permission_url, {"action": "request"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "already member")

    def test_add_user_by_admin(self):
        target_user = UserFactory(email="test@example.com")
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self.permission_url,
            {"action": "add-user", "email": "test@example.com", "role": "booker"},
        )

        assert response.status_code == HTTPStatus.FOUND  # Redirect

        # Check that permission was created
        permission = BookingPermission.objects.filter(
            user=target_user, organization=self.organization
        ).first()
        assert permission
        assert permission.status == BookingPermission.Status.CONFIRMED
        assert permission.role == BookingPermission.Role.BOOKER

    def test_add_user_by_admin_admin_role(self):
        target_user = UserFactory(email="admin@example.com")
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self.permission_url,
            {"action": "add-user", "email": "admin@example.com", "role": "admin"},
        )

        assert response.status_code == HTTPStatus.FOUND  # Redirect

        # Check that permission was created with admin role
        permission = BookingPermission.objects.filter(
            user=target_user, organization=self.organization
        ).first()
        assert permission
        assert permission.role == BookingPermission.Role.ADMIN

    def test_add_user_by_non_admin(self):
        regular_user = UserFactory()
        BookingPermissionFactory(
            user=regular_user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(regular_user)

        response = self.client.post(
            self.permission_url,
            {"action": "add-user", "email": "test@example.com", "role": "booker"},
        )

        assert response.status_code == HTTPStatus.FOUND  # Redirect with error message

    def test_add_nonexistent_user(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            self.permission_url,
            {
                "action": "add-user",
                "email": "nonexistent@example.com",
                "role": "booker",
            },
        )

        assert response.status_code == HTTPStatus.FOUND  # Redirect with error message

    def test_unauthenticated_access(self):
        response = self.client.post(self.permission_url, {"action": "request"})
        assert response.status_code == HTTPStatus.FOUND  # Redirect to login


class TestOrganizationPermissionManagementView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.admin_user = UserFactory()
        self.organization = OrganizationFactory()
        self.management_url = reverse(
            "organizations:organization-permissions-manage",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

        # Create admin permission for admin_user
        BookingPermissionFactory(
            user=self.admin_user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

    def test_confirm_permission(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.PENDING,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {"action": "confirm"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "has been confirmed")

        # Check that permission was confirmed
        permission = BookingPermission.objects.get(
            user=self.user, organization=self.organization
        )
        assert permission.status == BookingPermission.Status.CONFIRMED

    def test_confirm_already_confirmed_permission(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {"action": "confirm"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "already been confirmed")

    def test_cancel_permission(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {"action": "cancel"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "has been cancelled")

        # Check that permission was deleted
        assert not BookingPermission.objects.filter(
            user=self.user, organization=self.organization
        ).exists()

    def test_cancel_permission_by_user_themselves(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.post(self.management_url, {"action": "cancel"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "has been cancelled")

    def test_promote_to_admin(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {"action": "promote"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "promoted to admin")

        # Check that role was changed
        permission = BookingPermission.objects.get(
            user=self.user, organization=self.organization
        )
        assert permission.role == BookingPermission.Role.ADMIN

    def test_demote_to_booker(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {"action": "demote"})

        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "demoted to booker")

        # Check that role was changed
        permission = BookingPermission.objects.get(
            user=self.user, organization=self.organization
        )
        assert permission.role == BookingPermission.Role.BOOKER

    def test_action_by_non_admin(self):
        regular_user = UserFactory()
        BookingPermissionFactory(
            user=regular_user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(regular_user)

        response = self.client.post(self.management_url, {"action": "confirm"})

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_invalid_action(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {"action": "invalid"})

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_missing_action(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(self.management_url, {})

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_unauthenticated_access(self):
        response = self.client.post(self.management_url, {"action": "confirm"})
        assert response.status_code == HTTPStatus.FOUND  # Redirect to login
