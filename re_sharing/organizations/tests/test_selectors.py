"""
Tests for organization selectors following HackSoft Django styleguide.
Selectors are pure data access functions - test only database reads.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.selectors import get_booking_permission
from re_sharing.organizations.selectors import get_filtered_organizations
from re_sharing.organizations.selectors import get_organization_booking_count
from re_sharing.organizations.selectors import get_user_by_email
from re_sharing.organizations.selectors import get_user_permissions_for_organization
from re_sharing.organizations.selectors import user_has_admin_permission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


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


class TestGetFilteredOrganizations(TestCase):
    def setUp(self):
        # Create organization groups
        self.group1 = OrganizationGroupFactory(name="Group 1")
        self.group2 = OrganizationGroupFactory(name="Group 2")
        self.group3 = OrganizationGroupFactory(name="Group 3")

        # Create confirmed organizations
        self.org1 = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.org1.organization_groups.add(self.group1)

        self.org2 = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.org2.organization_groups.add(self.group2)

        self.org3 = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.org3.organization_groups.add(self.group1, self.group3)

        # Create pending organization (should be excluded)
        self.org_pending = OrganizationFactory(status=Organization.Status.PENDING)
        self.org_pending.organization_groups.add(self.group1)

    def test_returns_only_confirmed_organizations(self):
        result = get_filtered_organizations()
        assert self.org1 in result
        assert self.org2 in result
        assert self.org3 in result
        assert self.org_pending not in result

    def test_filter_by_include_groups(self):
        result = get_filtered_organizations(include_groups=[self.group1.id])
        assert self.org1 in result
        assert self.org3 in result
        assert self.org2 not in result

    def test_filter_by_exclude_groups(self):
        result = get_filtered_organizations(exclude_groups=[self.group2.id])
        assert self.org1 in result
        assert self.org3 in result
        assert self.org2 not in result

    def test_filter_by_both_include_and_exclude(self):
        result = get_filtered_organizations(
            include_groups=[self.group1.id],
            exclude_groups=[self.group3.id],
        )
        assert self.org1 in result
        assert self.org2 not in result
        assert self.org3 not in result

    def test_filter_by_booking_count(self):
        # Create bookings for org1
        now = timezone.now()
        for _ in range(3):
            BookingFactory(
                organization=self.org1,
                status=BookingStatus.CONFIRMED,
                timespan=(now, now + timedelta(hours=1)),
                total_amount=100,
            )

        # Create only 1 booking for org2
        BookingFactory(
            organization=self.org2,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=50,
        )

        result = get_filtered_organizations(min_bookings=2, months=1)
        assert self.org1 in result
        assert self.org2 not in result
        assert self.org3 not in result

        # Check that total_amount is annotated
        org1_result = result.get(id=self.org1.id)
        assert org1_result.booking_count == 3  # noqa: PLR2004
        assert org1_result.total_amount == 300  # noqa: PLR2004

    def test_filter_excludes_old_bookings(self):
        now = timezone.now()
        old_date = now - timedelta(days=120)

        # Create old booking for org1
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=(old_date, old_date + timedelta(hours=1)),
        )

        # Create recent booking for org2
        BookingFactory(
            organization=self.org2,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
        )

        result = get_filtered_organizations(min_bookings=1, months=3)
        assert self.org1 not in result
        assert self.org2 in result

    def test_filter_excludes_cancelled_bookings(self):
        now = timezone.now()

        # Create cancelled booking for org1
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CANCELLED,
            timespan=(now, now + timedelta(hours=1)),
        )

        result = get_filtered_organizations(min_bookings=1, months=1)
        assert self.org1 not in result

    def test_complex_filter_combination(self):
        now = timezone.now()

        # org1: in group1, has 2 bookings
        for _ in range(2):
            BookingFactory(
                organization=self.org1,
                status=BookingStatus.CONFIRMED,
                timespan=(now, now + timedelta(hours=1)),
            )

        # org2: in group2, has 3 bookings
        for _ in range(3):
            BookingFactory(
                organization=self.org2,
                status=BookingStatus.CONFIRMED,
                timespan=(now, now + timedelta(hours=1)),
            )

        result = get_filtered_organizations(
            include_groups=[self.group1.id, self.group2.id],
            exclude_groups=[self.group3.id],
            min_bookings=2,
            months=1,
        )

        assert self.org1 in result
        assert self.org2 in result
        assert self.org3 not in result


class TestGetOrganizationBookingCount(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)

    def test_counts_confirmed_bookings_only(self):
        now = timezone.now()

        # Create confirmed bookings
        for _ in range(3):
            BookingFactory(
                organization=self.organization,
                status=BookingStatus.CONFIRMED,
                timespan=(now, now + timedelta(hours=1)),
            )

        # Create cancelled booking (should not be counted)
        BookingFactory(
            organization=self.organization,
            status=BookingStatus.CANCELLED,
            timespan=(now, now + timedelta(hours=1)),
        )

        # Create pending booking (should not be counted)
        BookingFactory(
            organization=self.organization,
            status=BookingStatus.PENDING,
            timespan=(now, now + timedelta(hours=1)),
        )

        count = get_organization_booking_count(self.organization, months=1)
        assert count == 3  # noqa: PLR2004

    def test_counts_only_bookings_in_timeframe(self):
        now = timezone.now()
        old_date = now - timedelta(days=120)

        # Create recent bookings
        for _ in range(2):
            BookingFactory(
                organization=self.organization,
                status=BookingStatus.CONFIRMED,
                timespan=(now, now + timedelta(hours=1)),
            )

        # Create old booking (outside timeframe)
        BookingFactory(
            organization=self.organization,
            status=BookingStatus.CONFIRMED,
            timespan=(old_date, old_date + timedelta(hours=1)),
        )

        count = get_organization_booking_count(self.organization, months=3)
        assert count == 2  # noqa: PLR2004

    def test_returns_zero_for_no_bookings(self):
        count = get_organization_booking_count(self.organization, months=1)
        assert count == 0


class TestGetFilteredOrganizationsWithTotalAmount(TestCase):
    def setUp(self):
        self.org1 = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.org2 = OrganizationFactory(status=Organization.Status.CONFIRMED)

    def test_annotates_with_total_amount_when_months_provided(self):
        now = timezone.now()

        # Create bookings with different amounts
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=100,
        )
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=150,
        )

        result = get_filtered_organizations(months=1)
        org1_result = result.get(id=self.org1.id)

        assert org1_result.booking_count == 2  # noqa: PLR2004
        assert org1_result.total_amount == 250  # noqa: PLR2004

    def test_total_amount_defaults_to_zero_for_no_bookings(self):
        result = get_filtered_organizations(months=1)
        org_result = result.get(id=self.org1.id)

        assert org_result.booking_count == 0
        assert org_result.total_amount == 0

    def test_total_amount_excludes_cancelled_bookings(self):
        now = timezone.now()

        # Create confirmed booking
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=100,
        )

        # Create cancelled booking (should not be counted)
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CANCELLED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=200,
        )

        result = get_filtered_organizations(months=1)
        org_result = result.get(id=self.org1.id)

        assert org_result.booking_count == 1
        assert org_result.total_amount == 100  # noqa: PLR2004

    def test_max_amount_filter_excludes_organizations_above_threshold(self):
        now = timezone.now()

        # org1 has total of 300
        for _ in range(3):
            BookingFactory(
                organization=self.org1,
                status=BookingStatus.CONFIRMED,
                timespan=(now, now + timedelta(hours=1)),
                total_amount=100,
            )

        # org2 has total of 150
        BookingFactory(
            organization=self.org2,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=150,
        )

        result = get_filtered_organizations(months=1, max_amount=200)

        # org1 should be excluded (300 > 200), org2 should be included (150 <= 200)
        assert self.org1 not in result
        assert self.org2 in result

    def test_max_amount_filter_includes_organizations_at_threshold(self):
        now = timezone.now()

        # org1 has exactly 200
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=(now, now + timedelta(hours=1)),
            total_amount=200,
        )

        result = get_filtered_organizations(months=1, max_amount=200)
        org_result = result.get(id=self.org1.id)

        assert org_result is not None
        assert org_result.total_amount == 200  # noqa: PLR2004

    def test_max_amount_without_months_requires_months(self):
        # max_amount filter requires months parameter
        result = get_filtered_organizations(max_amount=100)

        # Without months, total_amount is not annotated, so filter has no effect
        # Organizations will be returned but without the annotation
        assert self.org1 in result
        assert self.org2 in result
