"""
Tests for organization selectors following HackSoft Django styleguide.
Selectors are pure data access functions - test only database reads.
"""

from django.test import TestCase

from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.selectors import get_booking_permission
from re_sharing.organizations.selectors import get_user_by_email
from re_sharing.organizations.selectors import get_user_permissions_for_organization
from re_sharing.organizations.selectors import user_has_admin_permission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.users.tests.factories import UserFactory


class TestGetBookingPermission(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.permission = BookingPermissionFactory(
            user=self.user, organization=self.organization
        )

    def test_get_existing_permission(self):
        result = get_booking_permission(self.organization, self.user.slug)
        assert result == self.permission

    def test_get_nonexistent_permission(self):
        other_user = UserFactory()
        result = get_booking_permission(self.organization, other_user.slug)
        assert result is None


class TestGetUserPermissionsForOrganization(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        # Note: Can't have multiple permissions for same user-org pair due to unique

    def test_get_all_user_permissions(self):
        # Create single permission (unique constraint prevents multiple)
        permission = BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        permissions = get_user_permissions_for_organization(
            self.user, self.organization
        )
        assert permissions.count() == 1
        assert permission in permissions

    def test_get_permissions_no_results(self):
        other_user = UserFactory()
        permissions = get_user_permissions_for_organization(
            other_user, self.organization
        )
        assert permissions.count() == 0


class TestUserHasAdminPermission(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.manager_user = UserFactory()
        self.organization = OrganizationFactory()

    def test_staff_user_has_admin_permission(self):
        result = user_has_admin_permission(self.staff_user, self.organization)
        assert result is True

    def test_manager_user_has_admin_permission(self):
        from re_sharing.providers.tests.factories import ManagerFactory

        # Create a proper manager for the user
        ManagerFactory(user=self.manager_user)
        result = user_has_admin_permission(self.manager_user, self.organization)
        assert result is True

    def test_admin_role_user_has_permission(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )
        result = user_has_admin_permission(self.user, self.organization)
        assert result is True

    def test_booker_role_user_no_admin_permission(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
            status=BookingPermission.Status.CONFIRMED,
        )
        result = user_has_admin_permission(self.user, self.organization)
        assert result is False

    def test_pending_admin_permission_no_access(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.PENDING,
        )
        result = user_has_admin_permission(self.user, self.organization)
        assert result is False

    def test_regular_user_no_permission(self):
        result = user_has_admin_permission(self.user, self.organization)
        assert result is False


class TestGetUserByEmail(TestCase):
    def setUp(self):
        self.user = UserFactory(email="test@example.com")

    def test_get_existing_user(self):
        result = get_user_by_email("test@example.com")
        assert result == self.user

    def test_get_nonexistent_user(self):
        result = get_user_by_email("nonexistent@example.com")
        assert result is None

    def test_case_sensitive_email(self):
        result = get_user_by_email("TEST@EXAMPLE.COM")
        assert result is None  # Django email field is case-sensitive by default
