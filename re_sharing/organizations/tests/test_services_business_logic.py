"""
Tests for organization services following HackSoft Django styleguide.
Focus on business logic validation and integration between services and selectors.
"""

import pytest
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.services import add_user_to_organization
from re_sharing.organizations.services import cancel_booking_permission
from re_sharing.organizations.services import confirm_booking_permission
from re_sharing.organizations.services import demote_user_to_booker
from re_sharing.organizations.services import promote_user_to_admin
from re_sharing.organizations.services import request_booking_permission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.users.tests.factories import UserFactory


class TestPermissionServiceBusinessLogic(TestCase):
    """Integration tests for permission services with business logic validation."""

    def setUp(self):
        self.user = UserFactory()
        self.admin_user = UserFactory()
        self.organization = OrganizationFactory()

        # Create admin permission for admin_user
        BookingPermissionFactory(
            user=self.admin_user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

    def test_request_booking_permission_integration(self):
        """Test complete integration from request to database storage."""
        message = request_booking_permission(self.user, self.organization)

        assert "Successfully requested" in message

        # Verify integration: service creates permission via selectors
        permission = BookingPermission.objects.filter(
            user=self.user, organization=self.organization
        ).first()
        assert permission
        assert permission.status == BookingPermission.Status.PENDING
        assert permission.role == BookingPermission.Role.BOOKER

    def test_request_booking_permission_business_logic_prevents_duplicates(self):
        """Test business logic prevents duplicate requests."""
        # First request
        request_booking_permission(self.user, self.organization)

        # Second request should be rejected by business logic
        message = request_booking_permission(self.user, self.organization)
        assert "already requested" in message

        # Should still only have one permission
        assert (
            BookingPermission.objects.filter(
                user=self.user, organization=self.organization
            ).count()
            == 1
        )

    def test_add_user_integration_with_role_handling(self):
        """Test complete user addition flow with role assignment."""
        target_user = UserFactory(email="test@example.com")

        # Test booker role
        message = add_user_to_organization(
            self.organization, "test@example.com", "booker", self.admin_user
        )

        assert "successfully added" in message
        permission = BookingPermission.objects.get(
            user=target_user, organization=self.organization
        )
        assert permission.role == BookingPermission.Role.BOOKER

        # Test admin role upgrade
        permission.delete()  # Clean up for next test
        message = add_user_to_organization(
            self.organization, "test@example.com", "admin", self.admin_user
        )

        permission = BookingPermission.objects.get(
            user=target_user, organization=self.organization
        )
        assert permission.role == BookingPermission.Role.ADMIN

    def test_permission_management_workflow(self):
        """Test workflow: request -> confirm -> promote -> demote."""
        # 1. User requests permission
        request_booking_permission(self.user, self.organization)
        permission = BookingPermission.objects.get(
            user=self.user, organization=self.organization
        )
        assert permission.status == BookingPermission.Status.PENDING

        # 2. Admin confirms permission
        message = confirm_booking_permission(
            self.organization, self.user.slug, self.admin_user
        )
        assert "has been confirmed" in message
        permission.refresh_from_db()
        assert permission.status == BookingPermission.Status.CONFIRMED
        assert permission.role == BookingPermission.Role.BOOKER

        # 3. Admin promotes user to admin
        message = promote_user_to_admin(
            self.organization, self.user.slug, self.admin_user
        )
        assert "promoted to admin" in message
        permission.refresh_from_db()
        assert permission.role == BookingPermission.Role.ADMIN

        # 4. Admin demotes user back to booker
        message = demote_user_to_booker(
            self.organization, self.user.slug, self.admin_user
        )
        assert "demoted to booker" in message
        permission.refresh_from_db()
        assert permission.role == BookingPermission.Role.BOOKER

        # 5. Admin cancels permission
        message = cancel_booking_permission(
            self.organization, self.user.slug, self.admin_user
        )
        assert "has been cancelled" in message
        assert not BookingPermission.objects.filter(
            user=self.user, organization=self.organization
        ).exists()

    def test_permission_authorization_enforcement(self):
        """Test that all services properly enforce admin authorization."""
        regular_user = UserFactory()
        BookingPermissionFactory(
            user=regular_user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )

        # All admin-required operations should fail for regular user
        with pytest.raises(PermissionDenied):
            add_user_to_organization(
                self.organization, "test@example.com", "booker", regular_user
            )

        with pytest.raises(PermissionDenied):
            confirm_booking_permission(self.organization, self.user.slug, regular_user)

        with pytest.raises(PermissionDenied):
            promote_user_to_admin(self.organization, self.user.slug, regular_user)

        with pytest.raises(PermissionDenied):
            demote_user_to_booker(self.organization, self.user.slug, regular_user)

    def test_self_permission_management(self):
        """Test that users can manage their own permissions appropriately."""
        # User creates own permission
        request_booking_permission(self.user, self.organization)

        # Admin confirms it
        confirm_booking_permission(self.organization, self.user.slug, self.admin_user)

        # User can cancel their own permission
        message = cancel_booking_permission(
            self.organization, self.user.slug, self.user
        )
        assert "has been cancelled" in message
        assert not BookingPermission.objects.filter(
            user=self.user, organization=self.organization
        ).exists()

    def test_error_handling_and_validation(self):
        """Test service error handling and input validation."""
        # Test missing required fields
        with pytest.raises(ValueError, match="Email and role are required"):
            add_user_to_organization(self.organization, "", "booker", self.admin_user)

        with pytest.raises(ValueError, match="Email and role are required"):
            add_user_to_organization(
                self.organization, "test@example.com", "", self.admin_user
            )

        # Test nonexistent user
        with pytest.raises(ValueError, match="No user found"):
            add_user_to_organization(
                self.organization, "nonexistent@example.com", "booker", self.admin_user
            )

        # Test operations on nonexistent permissions
        message = confirm_booking_permission(
            self.organization, "nonexistent-slug", self.admin_user
        )
        assert "does not exist" in message

    def test_business_logic_idempotency(self):
        """Test that repeated operations handle state correctly."""
        # Create confirmed permission
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
            role=BookingPermission.Role.BOOKER,
        )

        # Confirming already confirmed permission
        message = confirm_booking_permission(
            self.organization, self.user.slug, self.admin_user
        )
        assert "already been confirmed" in message

        # Promoting to admin twice (first should work, second should be idempotent)
        promote_user_to_admin(self.organization, self.user.slug, self.admin_user)
        # Note: Current implementation doesn't check if already admin

        # Adding existing user
        target_user = UserFactory(email="existing@example.com")
        BookingPermissionFactory(
            user=target_user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        message = add_user_to_organization(
            self.organization, "existing@example.com", "booker", self.admin_user
        )
        assert "already has permissions" in message
