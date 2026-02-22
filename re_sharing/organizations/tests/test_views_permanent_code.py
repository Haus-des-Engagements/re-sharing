"""Tests for permanent code management views."""

from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.models import PermanentCode
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import PermanentCodeFactory
from re_sharing.users.tests.factories import UserFactory


class TestManagerPermanentCodeActionView(TestCase):
    """Test the manager permanent code action view."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.manager_user = UserFactory()
        self.manager = ManagerFactory(user=self.manager_user)
        self.url = reverse(
            "organizations:manager-permanent-code-action",
            kwargs={"organization_slug": self.organization.slug},
        )

        # Create required accesses
        self.access1 = AccessFactory(id=1)
        self.access2 = AccessFactory(id=2)
        self.access8 = AccessFactory(id=8)

    def test_create_permanent_code_requires_manager(self):
        """Test that create action requires manager authentication."""
        regular_user = UserFactory()
        self.client.force_login(regular_user)

        response = self.client.post(self.url, data={"action": "create"})

        assert response.status_code == HTTPStatus.FORBIDDEN  # Permission denied

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    @patch(
        "re_sharing.resources.services_permanent_code.send_permanent_code_created_email"
    )
    def test_create_permanent_code_success(self, mock_email, mock_generate_code):
        """Test successful permanent code creation."""
        mock_generate_code.return_value = "123456"

        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url, data={"action": "create"}, headers={"hx-request": "true"}
        )

        assert response.status_code == HTTPStatus.OK

        # Verify code was created
        permanent_code = PermanentCode.objects.get(organization=self.organization)
        assert permanent_code.code == "123456"

        # Verify email was queued
        mock_email.enqueue.assert_called_once()

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    def test_create_permanent_code_fails_when_active_code_exists(
        self, mock_generate_code
    ):
        """Test that creating a code fails when an active code exists."""
        # Create existing code
        PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url, data={"action": "create"}, headers={"hx-request": "true"}
        )

        # Should return error
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_invalidate_permanent_code_success(self):
        """Test successful permanent code invalidation."""
        permanent_code = PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        validity_end = timezone.now() + timedelta(days=7)
        validity_end_str = validity_end.strftime("%Y-%m-%dT%H:%M")

        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url,
            data={
                "action": "invalidate",
                "permanent_code_id": permanent_code.id,
                "validity_end": validity_end_str,
            },
            headers={"hx-request": "true"},
        )

        assert response.status_code == HTTPStatus.OK

        # Verify code was invalidated
        permanent_code.refresh_from_db()
        assert permanent_code.validity_end is not None

    def test_invalidate_permanent_code_immediately(self):
        """Test invalidating a code immediately (empty validity_end)."""
        permanent_code = PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url,
            data={
                "action": "invalidate",
                "permanent_code_id": permanent_code.id,
                "validity_end": "",
            },
            headers={"hx-request": "true"},
        )

        assert response.status_code == HTTPStatus.OK

        # Verify code was invalidated immediately
        permanent_code.refresh_from_db()
        assert permanent_code.validity_end is not None
        # Should be very close to now
        time_diff = abs((permanent_code.validity_end - timezone.now()).total_seconds())
        assert time_diff < 2  # Within 2 seconds  # noqa: PLR2004

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    @patch(
        "re_sharing.resources.services_permanent_code.send_permanent_code_renewed_email"
    )
    def test_renew_permanent_code_success(self, mock_email, mock_generate_code):
        """Test successful permanent code renewal."""
        mock_generate_code.return_value = "654321"

        old_code = PermanentCodeFactory(
            organization=self.organization,
            code="111111",
            validity_start=timezone.now() - timedelta(days=30),
            validity_end=None,
            accesses=[self.access1, self.access2],
        )

        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url,
            data={
                "action": "renew",
                "permanent_code_id": old_code.id,
            },
            headers={"hx-request": "true"},
        )

        assert response.status_code == HTTPStatus.OK

        # Verify old code was updated
        old_code.refresh_from_db()
        assert old_code.validity_end is not None

        # Verify new code was created
        new_code = PermanentCode.objects.get(
            organization=self.organization, code="654321"
        )
        assert new_code.validity_end is None

        # Verify email was queued
        mock_email.enqueue.assert_called_once()

    def test_invalid_action_returns_bad_request(self):
        """Test that an invalid action returns bad request."""
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url, data={"action": "invalid_action"}, headers={"hx-request": "true"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_missing_action_returns_bad_request(self):
        """Test that missing action parameter returns bad request."""
        self.client.force_login(self.manager_user)
        response = self.client.post(self.url, headers={"hx-request": "true"})

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_returns_updated_organization_item_partial(self):
        """Test that the view returns the organization-item partial."""
        self.client.force_login(self.manager_user)

        # Create code first
        PermanentCodeFactory(
            organization=self.organization,
            code="123456",
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        # Invalidate with future date so code remains in active list
        future_date = timezone.now() + timedelta(days=7)
        response = self.client.post(
            self.url,
            data={
                "action": "invalidate",
                "permanent_code_id": PermanentCode.objects.first().id,
                "validity_end": future_date.strftime("%Y-%m-%dT%H:%M"),
            },
            headers={"hx-request": "true"},
        )

        # Response should include the permanent code with expiry date in the content
        assert response.status_code == HTTPStatus.OK
        assert b"123456" in response.content
        # Should show the expiry date
        expected_date = future_date.strftime("%d.%m.%Y").encode()
        assert expected_date in response.content


class TestManagerPermanentCodePermissions(TestCase):
    """Test permissions for permanent code management."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.manager_user = UserFactory()
        self.manager = ManagerFactory(user=self.manager_user)
        self.access1 = AccessFactory(id=1)
        self.url = reverse(
            "organizations:manager-permanent-code-action",
            kwargs={"organization_slug": self.organization.slug},
        )

    def test_staff_user_cannot_manage_permanent_codes(self):
        """Test that staff users without manager role cannot manage codes."""
        staff_user = UserFactory(is_staff=True)
        self.client.force_login(staff_user)

        response = self.client.post(self.url, data={"action": "create"})

        # Should get permission denied (no manager profile)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_anonymous_user_cannot_manage_permanent_codes(self):
        """Test that anonymous users cannot manage codes."""
        response = self.client.post(self.url, data={"action": "create"})

        # Should redirect to login
        assert response.status_code == HTTPStatus.FOUND


class TestPermanentCodeHTMXIntegration(TestCase):
    """Test HTMX-specific behavior for permanent code views."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.manager_user = UserFactory()
        self.manager = ManagerFactory(user=self.manager_user)
        self.access1 = AccessFactory(id=1)
        self.access2 = AccessFactory(id=2)
        self.access8 = AccessFactory(id=8)
        self.url = reverse(
            "organizations:manager-permanent-code-action",
            kwargs={"organization_slug": self.organization.slug},
        )

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    def test_htmx_request_returns_partial(self, mock_generate_code):
        """Test that HTMX requests return only the partial content."""
        mock_generate_code.return_value = "123456"

        self.client.force_login(self.manager_user)
        response = self.client.post(
            self.url, data={"action": "create"}, headers={"hx-request": "true"}
        )

        assert response.status_code == HTTPStatus.OK
        # Should contain organization data but not full page HTML
        assert b"123456" in response.content
        # Should not contain full page elements
        assert b"<!DOCTYPE html>" not in response.content
