from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.messages import get_messages
from django.core import mail
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.models import OrganizationMessage
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationMessageFactory
from re_sharing.organizations.views import list_organizations_view
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


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


def _confirmed_booking(organization, day, hour=10, **kwargs):
    start = timezone.make_aware(datetime.combine(day, time(hour)))
    kwargs.setdefault("status", BookingStatus.CONFIRMED)
    return BookingFactory(
        organization=organization,
        timespan=(start, start + timedelta(minutes=30)),
        **kwargs,
    )


class TestCustomOrganizationEmailView(TestCase):
    def setUp(self):
        from re_sharing.providers.tests.factories import ManagerFactory

        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.custom_email_url = reverse("organizations:custom-organization-email")
        self.org = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.room = ResourceFactory(
            name="Room A", type=Resource.ResourceTypeChoices.ROOM
        )
        self.parking = ResourceFactory(
            name="Parking P", type=Resource.ResourceTypeChoices.PARKING_LOT
        )
        self.item = ResourceFactory(
            name="Beamer", type=Resource.ResourceTypeChoices.LENDABLE_ITEM
        )

    def test_url_accessible_for_manager(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url)
        assert response.status_code == HTTPStatus.OK

    def test_view_renders_correct_template(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url)
        self.assertTemplateUsed(
            response, "organizations/custom_organization_email.html"
        )

    def test_unauthenticated_access_redirects(self):
        response = self.client.get(self.custom_email_url)
        assert response.status_code == HTTPStatus.FOUND  # Redirect to login

    def test_non_manager_is_denied(self):
        self.client.force_login(UserFactory())
        response = self.client.get(self.custom_email_url)
        assert response.status_code != HTTPStatus.OK

    def test_empty_form_lists_nothing(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url)
        assert list(response.context["organizations"]) == []

    def test_context_offers_rooms_and_parking_lots_only(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url)
        resources = list(response.context["filterable_resources"])
        assert self.room in resources
        assert self.parking in resources
        assert self.item not in resources

    def test_date_range_and_resources_narrow_the_preview(self):
        _confirmed_booking(self.org, date(2026, 3, 5), resource=self.room)
        _confirmed_booking(self.org, date(2026, 3, 6), resource=self.parking)
        _confirmed_booking(self.org, date(2026, 5, 1), resource=self.room)

        self.client.force_login(self.manager_user)
        response = self.client.get(
            self.custom_email_url,
            {
                "from_date": "2026-03-01",
                "to_date": "2026-03-31",
                "resources": [self.room.id],
            },
        )

        assert response.status_code == HTTPStatus.OK
        org = response.context["organizations"].get(id=self.org.id)
        assert org.booking_count == 1
        assert response.context["from_date"] == "2026-03-01"
        assert response.context["to_date"] == "2026-03-31"
        assert response.context["selected_resources"] == [str(self.room.id)]

    def test_no_dates_gives_all_time_statistics(self):
        _confirmed_booking(self.org, date(2020, 1, 1))
        _confirmed_booking(self.org, date(2030, 1, 1))

        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url, {"min_bookings": "2"})

        org = response.context["organizations"].get(id=self.org.id)
        assert org.booking_count == 2  # noqa: PLR2004

    def test_min_bookings_zero_is_honoured(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url, {"min_bookings": "0"})

        assert self.org in response.context["organizations"]

    def test_from_date_after_to_date_shows_error_and_no_list(self):
        _confirmed_booking(self.org, date(2026, 3, 5))

        self.client.force_login(self.manager_user)
        response = self.client.get(
            self.custom_email_url,
            {"from_date": "2026-04-01", "to_date": "2026-03-01"},
        )

        assert response.status_code == HTTPStatus.OK
        assert list(response.context["organizations"]) == []
        messages = list(get_messages(response.wsgi_request))
        assert any("from date" in str(m).lower() for m in messages)

    def test_invalid_date_shows_error(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url, {"from_date": "not-a-date"})

        assert response.status_code == HTTPStatus.OK
        assert list(response.context["organizations"]) == []
        messages = list(get_messages(response.wsgi_request))
        assert any("date" in str(m).lower() for m in messages)

    def test_page_renders_new_filters_and_not_months(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.custom_email_url)
        content = response.content.decode()

        assert 'name="from_date"' in content
        assert 'name="to_date"' in content
        assert 'name="resources"' in content
        assert 'name="months"' not in content
        assert "<optgroup" in content
        assert "Beamer" not in content


class TestSendCustomOrganizationEmailView(TestCase):
    def setUp(self):
        from re_sharing.providers.tests.factories import ManagerFactory

        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.send_email_url = reverse("organizations:send-custom-organization-email")
        self.org = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.room = ResourceFactory(
            name="Room A", type=Resource.ResourceTypeChoices.ROOM
        )

    def test_url_requires_post(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self.send_email_url)
        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_view_requires_authentication(self):
        response = self.client.post(self.send_email_url)
        assert response.status_code == HTTPStatus.FOUND  # Redirect to login

    def test_view_requires_selected_organizations(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.send_email_url,
            {
                "subject": "Test",
                "body": "Test body",
                "from_date": "2026-03-01",
            },
        )
        assert response.status_code == HTTPStatus.FOUND
        messages = list(get_messages(response.wsgi_request))
        assert any("select at least one" in str(m).lower() for m in messages)

    def test_view_requires_subject_and_body(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.send_email_url,
            {"subject": "", "body": "", "selected_orgs": [self.org.id]},
        )
        assert response.status_code == HTTPStatus.FOUND
        messages = list(get_messages(response.wsgi_request))
        assert any("subject and body" in str(m).lower() for m in messages)

    def test_sends_email_rendered_with_filter_context(self):
        _confirmed_booking(
            self.org, date(2026, 3, 5), resource=self.room, total_amount=10
        )
        _confirmed_booking(
            self.org, date(2026, 3, 6), resource=self.room, total_amount=20
        )
        _confirmed_booking(
            self.org, date(2026, 5, 1), resource=self.room, total_amount=99
        )

        self.client.force_login(self.manager_user)
        with override_settings(LANGUAGE_CODE="de"):
            response = self.client.post(
                self.send_email_url,
                {
                    "subject": "Hi {{ organization.name }}",
                    "body": "{{ number_of_bookings }}|{{ total_amount }}|"
                    "{{ from_date }}|{{ to_date }}|{{ min_bookings }}|{{ max_amount }}",
                    "from_date": "2026-03-01",
                    "to_date": "2026-03-31",
                    "resources": [self.room.id],
                    "min_bookings": "0",
                    "max_amount": "250.50",
                    "selected_orgs": [self.org.id],
                },
            )

        assert response.status_code == HTTPStatus.FOUND
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == f"Hi {self.org.name}"
        assert mail.outbox[0].body == "2|30,00|01.03.2026|31.03.2026|0|250,5"
        messages = list(get_messages(response.wsgi_request))
        assert any("enqueued 1" in str(m).lower() for m in messages)

    def test_email_without_dates_uses_all_time_statistics(self):
        _confirmed_booking(self.org, date(2020, 1, 1))
        _confirmed_booking(self.org, date(2030, 1, 1))

        self.client.force_login(self.manager_user)
        self.client.post(
            self.send_email_url,
            {
                "subject": "S",
                "body": "{{ number_of_bookings }}|[{{ from_date }}][{{ to_date }}]",
                "selected_orgs": [self.org.id],
            },
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].body == "2|[][]"

    def test_invalid_range_redirects_and_sends_nothing(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.send_email_url,
            {
                "subject": "S",
                "body": "B",
                "from_date": "2026-04-01",
                "to_date": "2026-03-01",
                "selected_orgs": [self.org.id],
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        assert len(mail.outbox) == 0
        messages = list(get_messages(response.wsgi_request))
        assert any("from date" in str(m).lower() for m in messages)

    def test_only_checked_and_matching_organizations_are_emailed(self):
        other = OrganizationFactory(status=Organization.Status.CONFIRMED)
        unchecked = OrganizationFactory(status=Organization.Status.CONFIRMED)
        _confirmed_booking(self.org, date(2026, 3, 5), resource=self.room)
        _confirmed_booking(other, date(2026, 3, 5), resource=ResourceFactory())
        _confirmed_booking(unchecked, date(2026, 3, 6), resource=self.room)

        self.client.force_login(self.manager_user)
        self.client.post(
            self.send_email_url,
            {
                "subject": "S",
                "body": "B",
                "min_bookings": "1",
                "resources": [self.room.id],
                "selected_orgs": [self.org.id, other.id],
            },
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [self.org.email]

    def test_no_matching_organization_warns(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.send_email_url,
            {
                "subject": "S",
                "body": "B",
                "min_bookings": "5",
                "selected_orgs": [self.org.id],
            },
        )

        assert len(mail.outbox) == 0
        messages = list(get_messages(response.wsgi_request))
        assert any("no organizations match" in str(m).lower() for m in messages)
