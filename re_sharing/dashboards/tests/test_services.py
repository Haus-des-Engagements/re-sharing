from datetime import date
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.dashboards.services import get_free_bookings_overview
from re_sharing.dashboards.services import get_users_bookings_and_permissions
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.users.models import User
from re_sharing.users.tests.factories import UserFactory


@pytest.mark.django_db()  # Mark for db access
@pytest.mark.parametrize(
    ("first_name", "expected_orgs", "expected_bookings"),
    [
        ("User1", [], []),
        ("User2", ["Org1"], ["Booking1", "Booking2"]),
        ("User3", ["Org1", "Org2"], ["Booking1", "Booking2", "Booking3"]),
    ],
)
def test_get_users_bookings_and_permissions(
    first_name, expected_orgs, expected_bookings
):
    UserFactory(first_name="User1")
    user2 = UserFactory(first_name="User2")
    user3 = UserFactory(first_name="User3")

    org1 = OrganizationFactory(name="Org1")
    org2 = OrganizationFactory(name="Org2")
    BookingFactory(
        title="Booking1",
        organization=org1,
        start_date=timezone.now().date() + timedelta(days=5),
    )
    BookingFactory(
        title="Booking2",
        organization=org1,
        start_date=timezone.now().date() + timedelta(days=5),
    )
    BookingFactory(
        title="Booking3",
        organization=org2,
        start_date=timezone.now().date() + timedelta(days=5),
    )
    BookingFactory(
        title="Booking4",
        organization=org2,
        start_date=timezone.now().date() - timedelta(days=5),
    )

    BookingPermissionFactory(organization=org1, user=user2)
    BookingPermissionFactory(organization=org1, user=user3)
    BookingPermissionFactory(organization=org2, user=user3)

    bookings, booking_permissions, equipment_loans = get_users_bookings_and_permissions(
        user=User.objects.get(first_name=first_name)
    )
    assert {
        organization.name
        for organization in {bp.organization for bp in booking_permissions}
    } == set(expected_orgs)
    assert {booking.title for booking in bookings} == set(expected_bookings)
    # equipment_loans should be empty as we didn't create any
    assert list(equipment_loans) == []


class TestGetFreeBookingsOverview(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.year = timezone.now().year
        self.organization = OrganizationFactory(name="Limited Org")
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )

    def limit(self, organization, valid_from):
        organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=5, free_bookings_valid_from=valid_from
            )
        )

    def use_free_bookings(self, organization, year, count):
        for i in range(count):
            BookingFactory(
                title=f"{organization.name}-{year}-{i}",
                organization=organization,
                start_date=date(year, 3, 1 + i),
                uses_free_booking=True,
            )

    def test_limited_organization_lists_current_and_following_year(self):
        self.limit(self.organization, date(2020, 1, 1))
        self.use_free_bookings(self.organization, self.year, 3)
        self.use_free_bookings(self.organization, self.year + 1, 5)

        overview = get_free_bookings_overview(user=self.user)

        assert overview == {
            self.organization.id: [
                {"year": self.year, "used": 3, "allowance": 5},
                {"year": self.year + 1, "used": 5, "allowance": 5},
            ]
        }

    def test_unlimited_organization_is_omitted(self):
        self.use_free_bookings(self.organization, self.year, 1)

        assert get_free_bookings_overview(user=self.user) == {}

    def test_year_before_the_valid_from_date_is_omitted(self):
        self.limit(self.organization, date(self.year + 1, 1, 1))
        self.use_free_bookings(self.organization, self.year + 1, 2)

        overview = get_free_bookings_overview(user=self.user)

        assert overview == {
            self.organization.id: [
                {"year": self.year + 1, "used": 2, "allowance": 5},
            ]
        }

    def test_organizations_without_confirmed_permission_are_omitted(self):
        other = OrganizationFactory(name="Other Org")
        self.limit(other, date(2020, 1, 1))
        BookingPermissionFactory(
            user=self.user, organization=other, status=BookingPermission.Status.PENDING
        )

        assert get_free_bookings_overview(user=self.user) == {}
