from datetime import timedelta

import pytest
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.dashboards.services import get_users_bookings_and_permissions
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
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

    bookings, booking_permissions = get_users_bookings_and_permissions(
        user=User.objects.get(first_name=first_name)
    )
    assert {
        organization.name
        for organization in {bp.organization for bp in booking_permissions}
    } == set(expected_orgs)
    assert {booking.title for booking in bookings} == set(expected_bookings)
