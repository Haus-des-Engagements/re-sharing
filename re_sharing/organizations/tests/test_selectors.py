"""
Tests for organization selectors following HackSoft Django styleguide.
Selectors are pure data access functions - test only database reads.
"""

from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.selectors import get_booking_permission
from re_sharing.organizations.selectors import get_custom_email_filterable_resources
from re_sharing.organizations.selectors import get_filtered_organizations
from re_sharing.organizations.selectors import get_free_bookings_allowance
from re_sharing.organizations.selectors import get_free_bookings_used
from re_sharing.organizations.selectors import get_organization_booking_stats
from re_sharing.organizations.selectors import get_remaining_free_bookings
from re_sharing.organizations.selectors import get_user_by_email
from re_sharing.organizations.selectors import get_user_permissions_for_organization
from re_sharing.organizations.selectors import is_free_bookings_allowance_limited_until
from re_sharing.organizations.selectors import user_has_admin_permission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import ResourceFactory
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


def local_dt(day: date, hour: int = 10, minute: int = 0) -> datetime:
    """Aware datetime on the given day in the project time zone."""
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def confirmed_booking(organization, day: date, hour=10, minute=0, **kwargs):
    start = local_dt(day, hour, minute)
    kwargs.setdefault("status", BookingStatus.CONFIRMED)
    return BookingFactory(
        organization=organization,
        timespan=(start, start + timedelta(minutes=30)),
        **kwargs,
    )


def room(name: str) -> Resource:
    return ResourceFactory(name=name, type=Resource.ResourceTypeChoices.ROOM)


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

        self.from_date = date(2026, 3, 1)
        self.to_date = date(2026, 3, 31)
        self.in_range = date(2026, 3, 15)

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
        for _ in range(3):
            confirmed_booking(self.org1, self.in_range, total_amount=100)
        confirmed_booking(self.org2, self.in_range, total_amount=50)

        result = get_filtered_organizations(
            min_bookings=2, from_date=self.from_date, to_date=self.to_date
        )
        assert self.org1 in result
        assert self.org2 not in result
        assert self.org3 not in result

        org1_result = result.get(id=self.org1.id)
        assert org1_result.booking_count == 3  # noqa: PLR2004
        assert org1_result.total_amount == 300  # noqa: PLR2004

    def test_filter_excludes_bookings_outside_range(self):
        confirmed_booking(self.org1, date(2025, 11, 1))
        confirmed_booking(self.org2, self.in_range)

        result = get_filtered_organizations(
            min_bookings=1, from_date=self.from_date, to_date=self.to_date
        )
        assert self.org1 not in result
        assert self.org2 in result

    def test_filter_excludes_cancelled_bookings(self):
        confirmed_booking(self.org1, self.in_range, status=BookingStatus.CANCELLED)

        result = get_filtered_organizations(
            min_bookings=1, from_date=self.from_date, to_date=self.to_date
        )
        assert self.org1 not in result

    def test_filter_excludes_pending_bookings(self):
        confirmed_booking(self.org1, self.in_range, status=BookingStatus.PENDING)

        result = get_filtered_organizations(min_bookings=1)
        assert self.org1 not in result

    def test_complex_filter_combination(self):
        for _ in range(2):
            confirmed_booking(self.org1, self.in_range, resource=ResourceFactory())
        for _ in range(3):
            confirmed_booking(self.org2, self.in_range, resource=ResourceFactory())

        result = get_filtered_organizations(
            include_groups=[self.group1.id, self.group2.id],
            exclude_groups=[self.group3.id],
            min_bookings=2,
            from_date=self.from_date,
            to_date=self.to_date,
        )

        assert self.org1 in result
        assert self.org2 in result
        assert self.org3 not in result

    # --- date range boundaries -------------------------------------------

    def _count(self, **kwargs) -> int:
        return get_filtered_organizations(**kwargs).get(id=self.org1.id).booking_count

    def test_booking_starting_at_start_of_from_date_counts(self):
        confirmed_booking(self.org1, self.from_date, hour=0, minute=0)
        assert self._count(from_date=self.from_date, to_date=self.to_date) == 1

    def test_booking_starting_late_on_to_date_counts(self):
        confirmed_booking(self.org1, self.to_date, hour=23, minute=30)
        assert self._count(from_date=self.from_date, to_date=self.to_date) == 1

    def test_booking_starting_day_after_to_date_does_not_count(self):
        confirmed_booking(self.org1, date(2026, 4, 1), hour=0, minute=0)
        assert self._count(from_date=self.from_date, to_date=self.to_date) == 0

    def test_booking_starting_day_before_from_date_does_not_count(self):
        confirmed_booking(self.org1, date(2026, 2, 28), hour=23, minute=59)
        assert self._count(from_date=self.from_date, to_date=self.to_date) == 0

    def test_booking_overlapping_into_range_but_starting_before_does_not_count(
        self,
    ):
        start = local_dt(date(2026, 2, 28), 22)
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=(start, start + timedelta(hours=4)),
        )
        assert self._count(from_date=self.from_date, to_date=self.to_date) == 0

    def test_only_from_date_is_open_ended(self):
        confirmed_booking(self.org1, date(2026, 2, 28))
        confirmed_booking(self.org1, self.from_date)
        confirmed_booking(self.org1, date(2030, 1, 1))
        assert self._count(from_date=self.from_date) == 2  # noqa: PLR2004

    def test_only_to_date_is_open_ended(self):
        confirmed_booking(self.org1, date(2020, 1, 1))
        confirmed_booking(self.org1, self.to_date)
        confirmed_booking(self.org1, date(2026, 4, 1))
        assert self._count(to_date=self.to_date) == 2  # noqa: PLR2004

    def test_no_dates_counts_all_time(self):
        confirmed_booking(self.org1, date(2020, 1, 1))
        confirmed_booking(self.org1, date(2026, 3, 1))
        confirmed_booking(self.org1, date(2030, 1, 1))
        assert self._count() == 3  # noqa: PLR2004

    def test_future_range_counts_future_confirmed_bookings(self):
        today = timezone.localdate()
        start = today + timedelta(days=30)
        end = today + timedelta(days=60)
        confirmed_booking(self.org1, start + timedelta(days=5))
        confirmed_booking(self.org1, end + timedelta(days=1))
        assert self._count(from_date=start, to_date=end) == 1

    # --- thresholds without a date range ----------------------------------

    def test_min_bookings_without_date_range(self):
        confirmed_booking(self.org1, date(2020, 1, 1))
        for _ in range(3):
            confirmed_booking(self.org2, date(2020, 1, 1))

        result = get_filtered_organizations(min_bookings=2)
        assert self.org1 not in result
        assert self.org2 in result

    def test_max_amount_without_date_range(self):
        confirmed_booking(self.org1, date(2020, 1, 1), total_amount=150)
        confirmed_booking(self.org2, date(2020, 1, 1), total_amount=50)

        result = get_filtered_organizations(max_amount=100)
        assert self.org1 not in result
        assert self.org2 in result

    def test_min_bookings_zero_is_honoured(self):
        result = get_filtered_organizations(min_bookings=0)
        assert self.org1 in result
        assert result.get(id=self.org1.id).booking_count == 0

    # --- resource filter --------------------------------------------------

    def test_selected_resource_narrows_count_and_amount(self):
        room_a = room("Room A")
        room_b = room("Room B")
        confirmed_booking(self.org1, self.in_range, resource=room_a, total_amount=10)
        confirmed_booking(
            self.org1, self.in_range, hour=12, resource=room_a, total_amount=20
        )
        confirmed_booking(self.org1, self.in_range, resource=room_b, total_amount=40)

        org = get_filtered_organizations(resource_ids=[room_a.id]).get(id=self.org1.id)
        assert org.booking_count == 2  # noqa: PLR2004
        assert org.total_amount == 30  # noqa: PLR2004

    def test_multiple_selected_resources_are_combined(self):
        room_a = room("Room A")
        room_b = room("Room B")
        parking = ResourceFactory(
            name="Parking P", type=Resource.ResourceTypeChoices.PARKING_LOT
        )
        confirmed_booking(self.org1, self.in_range, resource=room_a)
        confirmed_booking(self.org1, self.in_range, resource=parking)
        confirmed_booking(self.org1, self.in_range, resource=room_b)

        assert self._count(resource_ids=[room_a.id, parking.id]) == 2  # noqa: PLR2004

    def test_no_selection_counts_all_resources(self):
        confirmed_booking(self.org1, self.in_range, resource=room("Room A"))
        confirmed_booking(self.org1, self.in_range, resource=room("Room B"))

        assert self._count(resource_ids=[]) == 2  # noqa: PLR2004
        assert self._count(resource_ids=None) == 2  # noqa: PLR2004

    def test_lendable_item_id_is_ignored(self):
        item = ResourceFactory(
            name="Beamer", type=Resource.ResourceTypeChoices.LENDABLE_ITEM
        )
        confirmed_booking(self.org1, self.in_range, resource=item)
        confirmed_booking(self.org1, self.in_range, resource=room("Room A"))

        assert self._count(resource_ids=[item.id]) == 0

    def test_resource_filter_combines_with_date_range(self):
        room_a = room("Room A")
        confirmed_booking(self.org1, self.in_range, resource=room_a)
        confirmed_booking(self.org1, date(2025, 1, 1), resource=room_a)
        confirmed_booking(self.org1, self.in_range, resource=room("Room B"))

        assert (
            self._count(
                from_date=self.from_date,
                to_date=self.to_date,
                resource_ids=[room_a.id],
            )
            == 1
        )

    def test_thresholds_use_narrowed_statistics(self):
        room_a = room("Room A")
        confirmed_booking(self.org1, self.in_range, resource=room_a)
        confirmed_booking(self.org1, self.in_range, resource=room("Room B"))
        confirmed_booking(self.org1, self.in_range, resource=room("Room C"))

        result = get_filtered_organizations(min_bookings=2, resource_ids=[room_a.id])
        assert self.org1 not in result


class TestGetCustomEmailFilterableResources(TestCase):
    def test_returns_rooms_and_parking_lots_ordered_by_type_then_name(self):
        room_b = room("Room B")
        room_a = room("Room A")
        parking = ResourceFactory(
            name="Parking P", type=Resource.ResourceTypeChoices.PARKING_LOT
        )
        ResourceFactory(name="Beamer", type=Resource.ResourceTypeChoices.LENDABLE_ITEM)

        result = list(get_custom_email_filterable_resources())

        assert result == [parking, room_a, room_b]


class TestGetOrganizationBookingStats(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.from_date = date(2026, 3, 1)
        self.to_date = date(2026, 3, 31)

    def test_matches_preview_for_same_filter(self):
        room_a = room("Room A")
        confirmed_booking(
            self.organization, date(2026, 3, 10), resource=room_a, total_amount=10
        )
        confirmed_booking(
            self.organization, date(2026, 3, 20), resource=room_a, total_amount=20
        )
        confirmed_booking(
            self.organization, date(2026, 3, 20), resource=room("B"), total_amount=99
        )
        confirmed_booking(
            self.organization, date(2026, 5, 1), resource=room_a, total_amount=99
        )

        stats = get_organization_booking_stats(
            self.organization,
            from_date=self.from_date,
            to_date=self.to_date,
            resource_ids=[room_a.id],
        )
        preview = get_filtered_organizations(
            from_date=self.from_date,
            to_date=self.to_date,
            resource_ids=[room_a.id],
        ).get(id=self.organization.id)

        assert stats == {"booking_count": 2, "total_amount": Decimal(30)}
        assert stats["booking_count"] == preview.booking_count
        assert stats["total_amount"] == preview.total_amount

    def test_all_time_when_no_dates(self):
        confirmed_booking(self.organization, date(2020, 1, 1), total_amount=1)
        confirmed_booking(self.organization, date(2030, 1, 1), total_amount=2)

        stats = get_organization_booking_stats(self.organization)

        assert stats == {"booking_count": 2, "total_amount": Decimal(3)}

    def test_total_amount_is_zero_when_nothing_matches(self):
        stats = get_organization_booking_stats(
            self.organization, from_date=self.from_date, to_date=self.to_date
        )

        assert stats == {"booking_count": 0, "total_amount": 0}

    def test_excludes_non_confirmed_bookings(self):
        confirmed_booking(self.organization, date(2026, 3, 5))
        confirmed_booking(
            self.organization, date(2026, 3, 5), status=BookingStatus.CANCELLED
        )
        confirmed_booking(
            self.organization, date(2026, 3, 5), status=BookingStatus.PENDING
        )

        stats = get_organization_booking_stats(self.organization)

        assert stats["booking_count"] == 1


class TestGetFilteredOrganizationsWithTotalAmount(TestCase):
    def setUp(self):
        self.org1 = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.org2 = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.day = date(2026, 3, 15)

    def test_annotates_with_total_amount(self):
        confirmed_booking(self.org1, self.day, total_amount=100)
        confirmed_booking(self.org1, self.day, total_amount=150)

        result = get_filtered_organizations()
        org1_result = result.get(id=self.org1.id)

        assert org1_result.booking_count == 2  # noqa: PLR2004
        assert org1_result.total_amount == 250  # noqa: PLR2004

    def test_total_amount_defaults_to_zero_for_no_bookings(self):
        result = get_filtered_organizations()
        org_result = result.get(id=self.org1.id)

        assert org_result.booking_count == 0
        assert org_result.total_amount == 0

    def test_total_amount_excludes_cancelled_bookings(self):
        confirmed_booking(self.org1, self.day, total_amount=100)
        confirmed_booking(
            self.org1, self.day, total_amount=200, status=BookingStatus.CANCELLED
        )

        result = get_filtered_organizations()
        org_result = result.get(id=self.org1.id)

        assert org_result.booking_count == 1
        assert org_result.total_amount == 100  # noqa: PLR2004

    def test_max_amount_filter_excludes_organizations_above_threshold(self):
        for _ in range(3):
            confirmed_booking(self.org1, self.day, total_amount=100)
        confirmed_booking(self.org2, self.day, total_amount=150)

        result = get_filtered_organizations(max_amount=200)

        assert self.org1 not in result
        assert self.org2 in result

    def test_max_amount_filter_includes_organizations_at_threshold(self):
        confirmed_booking(self.org1, self.day, total_amount=200)

        result = get_filtered_organizations(max_amount=200)
        org_result = result.get(id=self.org1.id)

        assert org_result is not None
        assert org_result.total_amount == 200  # noqa: PLR2004


class TestFreeBookingsAllowanceSelectors(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.limited_group = OrganizationGroupFactory(
            free_bookings_per_year=5, free_bookings_valid_from=date(2027, 1, 1)
        )

    def test_organization_without_limited_group_is_unlimited(self):
        self.organization.organization_groups.add(OrganizationGroupFactory())

        assert get_free_bookings_allowance(self.organization, date(2027, 6, 1)) is None

    def test_organization_without_any_group_is_unlimited(self):
        assert get_free_bookings_allowance(self.organization, date(2027, 6, 1)) is None

    def test_allowance_is_unlimited_before_the_valid_from_date(self):
        self.organization.organization_groups.add(self.limited_group)

        assert (
            get_free_bookings_allowance(self.organization, date(2026, 12, 31)) is None
        )

    def test_allowance_is_limited_from_the_valid_from_date(self):
        self.organization.organization_groups.add(self.limited_group)

        assert get_free_bookings_allowance(self.organization, date(2027, 1, 1)) == 5  # noqa: PLR2004

    def test_highest_number_wins_among_limited_groups(self):
        self.organization.organization_groups.add(self.limited_group)
        self.organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=12, free_bookings_valid_from=date(2027, 1, 1)
            )
        )

        assert get_free_bookings_allowance(self.organization, date(2027, 3, 1)) == 12  # noqa: PLR2004

    def test_one_unlimited_group_makes_the_organization_unlimited(self):
        self.organization.organization_groups.add(self.limited_group)
        self.organization.organization_groups.add(OrganizationGroupFactory())

        assert get_free_bookings_allowance(self.organization, date(2027, 3, 1)) is None

    def test_limited_until_is_false_before_the_valid_from_date(self):
        self.organization.organization_groups.add(self.limited_group)

        assert (
            is_free_bookings_allowance_limited_until(
                self.organization, date(2026, 12, 20)
            )
            is False
        )

    def test_limited_until_is_true_on_and_after_the_valid_from_date(self):
        self.organization.organization_groups.add(self.limited_group)

        assert is_free_bookings_allowance_limited_until(
            self.organization, date(2027, 1, 1)
        )
        assert is_free_bookings_allowance_limited_until(
            self.organization, date(2028, 10, 1)
        )

    def test_limited_until_is_false_for_unlimited_organizations(self):
        self.organization.organization_groups.add(OrganizationGroupFactory())

        assert (
            is_free_bookings_allowance_limited_until(
                self.organization, date(2028, 10, 1)
            )
            is False
        )


class TestFreeBookingsUsedSelectors(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=5, free_bookings_valid_from=date(2027, 1, 1)
            )
        )

    def _free_booking(self, title, **kwargs):
        kwargs.setdefault("start_date", date(2027, 3, 1))
        kwargs.setdefault("status", BookingStatus.CONFIRMED)
        return BookingFactory(
            title=title,
            organization=self.organization,
            uses_free_booking=True,
            **kwargs,
        )

    def test_pending_and_confirmed_bookings_count_one_each(self):
        self._free_booking(
            "short", status=BookingStatus.PENDING, start_time=time(9), end_time=time(10)
        )
        self._free_booking("long", start_time=time(9), end_time=time(17))

        assert get_free_bookings_used(self.organization, 2027) == 2  # noqa: PLR2004

    def test_cancelled_and_unavailable_bookings_do_not_count(self):
        self._free_booking("cancelled", status=BookingStatus.CANCELLED)
        self._free_booking("unavailable", status=BookingStatus.UNAVAILABLE)

        assert get_free_bookings_used(self.organization, 2027) == 0

    def test_bookings_without_the_flag_do_not_count(self):
        BookingFactory(
            title="legacy",
            organization=self.organization,
            start_date=date(2027, 3, 1),
            uses_free_booking=False,
        )

        assert get_free_bookings_used(self.organization, 2027) == 0

    def test_bookings_of_other_years_do_not_count(self):
        self._free_booking("this-year")
        self._free_booking("other-year", start_date=date(2028, 3, 1))

        assert get_free_bookings_used(self.organization, 2027) == 1

    def test_bookings_of_other_organizations_do_not_count(self):
        BookingFactory(
            title="foreign",
            start_date=date(2027, 3, 1),
            uses_free_booking=True,
        )

        assert get_free_bookings_used(self.organization, 2027) == 0

    def test_excluded_booking_is_skipped(self):
        excluded = self._free_booking("excluded")
        self._free_booking("counted")

        assert get_free_bookings_used(self.organization, 2027) == 2  # noqa: PLR2004
        assert (
            get_free_bookings_used(self.organization, 2027, exclude_booking=excluded)
            == 1
        )

    def test_remaining_is_unlimited_for_unlimited_organizations(self):
        unlimited = OrganizationFactory()

        assert get_remaining_free_bookings(unlimited, date(2027, 3, 1)) is None

    def test_remaining_subtracts_used_free_bookings(self):
        self._free_booking("one")
        self._free_booking("two")

        assert get_remaining_free_bookings(self.organization, date(2027, 6, 1)) == 3  # noqa: PLR2004

    def test_remaining_excludes_a_given_booking(self):
        booking = self._free_booking("one")

        assert (
            get_remaining_free_bookings(
                self.organization, date(2027, 6, 1), exclude_booking=booking
            )
            == 5  # noqa: PLR2004
        )

    def test_remaining_is_unlimited_before_the_valid_from_date(self):
        self._free_booking("one")

        assert (
            get_remaining_free_bookings(self.organization, date(2026, 12, 31)) is None
        )

    def test_remaining_floors_at_zero_when_the_allowance_was_lowered(self):
        for i in range(5):
            self._free_booking(f"booking-{i}")
        group = self.organization.organization_groups.get()
        group.free_bookings_per_year = 3
        group.save()

        assert get_remaining_free_bookings(self.organization, date(2027, 6, 1)) == 0

    def test_organization_leaving_its_unlimited_group_gets_the_full_allowance(self):
        unlimited_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(unlimited_group)
        for i in range(10):
            BookingFactory(
                title=f"unlimited-{i}",
                organization=self.organization,
                start_date=date(2027, 3, 1),
                uses_free_booking=False,
            )

        self.organization.organization_groups.remove(unlimited_group)

        assert get_remaining_free_bookings(self.organization, date(2027, 6, 1)) == 5  # noqa: PLR2004
