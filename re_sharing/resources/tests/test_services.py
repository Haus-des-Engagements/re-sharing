import datetime
from datetime import timedelta
from unittest import skip
from zoneinfo import ZoneInfo

import pytest
from django.test import TestCase
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.services import filter_resources
from re_sharing.resources.services import get_access_code
from re_sharing.resources.services import get_user_accessible_locations
from re_sharing.resources.services import planner
from re_sharing.resources.services import show_resource
from re_sharing.resources.tests.factories import AccessCodeFactory
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import LocationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


class GetWeeklyBookingsTest(TestCase):
    def test_empty_weekly_bookings(self):
        date = timezone.make_aware(timezone.datetime(2024, 7, 23))

        resource = ResourceFactory()
        date_string = date.strftime("%Y-%m-%d")
        resource, time_slots, weekdays, dates, compensations, restrictions = (
            show_resource(resource.slug, date_string)
        )

        # Check the length of returned lists
        number_of_timeslots = 36
        assert len(time_slots) == number_of_timeslots
        number_of_weekdays = 7
        assert len(weekdays) == number_of_weekdays

        # Check some sample values
        assert time_slots[0]["time"] == timezone.datetime(
            2024, 7, 22, 6, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
        )
        assert time_slots[0]["booked"] == [
            "?starttime=06:00&endtime=07:30&startdate=2024-07-22&resource="
            + resource.slug,
            "?starttime=06:00&endtime=07:30&startdate=2024-07-23&resource="
            + resource.slug,
            "?starttime=06:00&endtime=07:30&startdate=2024-07-24&resource="
            + resource.slug,
            "?starttime=06:00&endtime=07:30&startdate=2024-07-25&resource="
            + resource.slug,
            "?starttime=06:00&endtime=07:30&startdate=2024-07-26&resource="
            + resource.slug,
            "?starttime=06:00&endtime=07:30&startdate=2024-07-27&resource="
            + resource.slug,
            "?starttime=06:00&endtime=07:30&startdate=2024-07-28&resource="
            + resource.slug,
        ]
        assert weekdays[0] == datetime.datetime(
            2024, 7, 22, 0, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
        )

        assert dates["shown_date"] == timezone.make_naive(date).date()
        assert (
            dates["previous_week"]
            == timezone.make_naive(date - timedelta(days=7)).date()
        )
        assert (
            dates["next_week"] == timezone.make_naive(date + timedelta(days=7)).date()
        )

    def test_some_bookings_exist(self):
        resource = ResourceFactory()
        booking1 = BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 8, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 9, 0)),
            ),
        )
        booking2 = BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 18, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 22, 0)),
            ),
        )
        booking1.save()
        booking2.save()

        date = timezone.make_aware(timezone.datetime(2024, 6, 5))

        date_string = date.strftime("%Y-%m-%d")
        resource, time_slots, weekdays, dates, compensations, restrictions = (
            show_resource(resource.slug, date_string)
        )

        number_of_timeslots = 36
        assert len(time_slots) == number_of_timeslots
        number_of_weekdays = 7
        assert len(weekdays) == number_of_weekdays

        assert (
            time_slots[4]["booked"][2] is True
        )  # This should be True because we booked the slot from 8:00 to 9:00
        assert (
            time_slots[14]["booked"][2] is not False
        )  # This should be False because we did not book the slot
        assert (
            time_slots[24]["booked"][2] is True
        )  # This should be True because we booked the slot from 18:00 to 22:00

    def test_without_date(self):
        date_string = None
        resource = ResourceFactory()
        resource, time_slots, weekdays, dates, compensations, restrictions = (
            show_resource(resource.slug, date_string)
        )
        today = timezone.now().date()
        start_of_week = today - datetime.timedelta(days=today.weekday())

        assert time_slots[0]["booked"] == [
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=0)}&resource=" + resource.slug,
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=1)}&resource=" + resource.slug,
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=2)}&resource=" + resource.slug,
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=3)}&resource=" + resource.slug,
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=4)}&resource=" + resource.slug,
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=5)}&resource=" + resource.slug,
            f"?starttime=06:00&endtime=07:30&startdate="
            f"{start_of_week + datetime.timedelta(days=6)}&resource=" + resource.slug,
        ]


@pytest.mark.django_db()  # Mark for db access
@pytest.mark.parametrize(
    ("persons_count", "start_datetime", "expected"),
    [
        ("2", None, ["Resource1", "Resource2"]),
        ("1", "2024-07-25T12:30", ["Resource1", "Resource2", "Small Resource"]),
        ("3", None, ["Resource2"]),
        (None, None, ["Resource1", "Resource2", "Small Resource"]),
    ],
)
def test_filter_resources(persons_count, start_datetime, expected):
    ResourceFactory.create(name="Resource1", max_persons=2)
    ResourceFactory.create(name="Resource2", max_persons=3)
    ResourceFactory.create(name="Small Resource", max_persons=1)
    user = UserFactory()

    resources = filter_resources(user, persons_count, start_datetime)
    assert {resource.name for resource in resources} == set(expected)


class TestGetAccessCode(TestCase):
    """
    Given an organization, resource and a timestamp,
    when I ask for an access code for that resource,
    I get back the correct code.
    """

    def setUp(self):
        self.timestamp = timezone.make_aware(timezone.datetime(2024, 7, 23, 13, 30))
        self.access1 = AccessFactory()
        self.access2 = AccessFactory()
        self.resource1 = ResourceFactory(access=self.access1)
        self.resource2 = ResourceFactory(access=self.access2)
        self.organization1 = OrganizationFactory()
        self.organization2 = OrganizationFactory()
        self.access_code1 = AccessCodeFactory(
            access=self.access1, validity_start=self.timestamp, organization=None
        )
        self.access_code2 = AccessCodeFactory(
            access=self.access1,
            validity_start=self.timestamp + timedelta(days=7),
            organization=self.organization2,
        )
        self.access_code3 = AccessCodeFactory(
            access=self.access1,
            validity_start=self.timestamp + timedelta(days=14),
            organization=None,
        )

    def test_get_general_access_code(self):
        # Gets access_code1 (general code) as there's no PermanentCode
        assert (
            get_access_code(
                resource_slug=self.resource1.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=1)),
            )
            == self.access_code1
        )

        # Should still get back access_code1 (general code)
        # Organization-specific AccessCodes are now ignored
        assert (
            get_access_code(
                resource_slug=self.resource1.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=10)),
            )
            == self.access_code1
        )

        # Even for organization2, should get general access_code1
        # (organization-specific AccessCode is no longer used)
        assert (
            get_access_code(
                resource_slug=self.resource1.slug,
                organization_slug=self.organization2.slug,
                timestamp=(self.timestamp + timedelta(days=10)),
            )
            == self.access_code1
        )

        # No access code exists for resource2/access2
        assert (
            get_access_code(
                resource_slug=self.resource2.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=1)),
            )
            is None
        )

    def test_get_permanent_code_takes_precedence(self):
        """Test that PermanentCode is returned when available."""
        from re_sharing.resources.tests.factories import PermanentCodeFactory

        # Create a permanent code for organization1 and access1
        permanent_code = PermanentCodeFactory(
            organization=self.organization1,
            validity_start=self.timestamp - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        # Even though there's an access_code1, the permanent code should be returned
        result = get_access_code(
            resource_slug=self.resource1.slug,
            organization_slug=self.organization1.slug,
            timestamp=(self.timestamp + timedelta(days=1)),
        )

        assert result == permanent_code

    def test_get_permanent_code_respects_validity_end(self):
        """Test that expired PermanentCode is not returned."""
        from re_sharing.resources.tests.factories import PermanentCodeFactory

        # Create an expired permanent code
        PermanentCodeFactory(
            organization=self.organization1,
            validity_start=self.timestamp - timedelta(days=10),
            validity_end=self.timestamp - timedelta(days=1),
            accesses=[self.access1],
        )

        # Should fall back to access_code1 since permanent code is expired
        result = get_access_code(
            resource_slug=self.resource1.slug,
            organization_slug=self.organization1.slug,
            timestamp=(self.timestamp + timedelta(days=1)),
        )

        assert result == self.access_code1


@skip
class TestResourcePlanner(TestCase):
    def test_empty_planner_table(self):
        date = timezone.make_aware(timezone.datetime(2024, 7, 23))
        date_string = date.strftime("%Y-%m-%d")

        resource1 = ResourceFactory()
        resource2 = ResourceFactory()
        user = UserFactory()
        resources, timeslots, dates = planner(user, date_string)

        number_of_timeslots = 48
        assert len(timeslots) == number_of_timeslots
        assert set(resources) == {resource1, resource2}

        # Check some sample values
        assert (
            dates["previous_day"]
            == timezone.make_naive(date - timedelta(days=1)).date()
        )
        assert dates["next_day"] == timezone.make_naive(date + timedelta(days=1)).date()
        assert dates["shown_date"] == timezone.make_naive(date).date()
        assert timeslots[16]["time"] == timezone.datetime(
            2024, 7, 23, 8, 0, tzinfo=ZoneInfo(key="Europe/Berlin")
        )

        booking_link1 = (
            "?starttime=08:00&endtime=09:30&startdate=2024-07-23&resource="
            + resource1.slug
        )
        booking_link2 = (
            "?starttime=08:00&endtime=09:30&startdate=2024-07-23&resource="
            + resource2.slug
        )
        assert timeslots[16]["slot"] == [
            {"booked": False, "booking_link": booking_link1},
            {"booked": False, "booking_link": booking_link2},
        ]

        # Check that every slot is False (not booked)
        for item in timeslots:
            assert all(resource["booked"] is False for resource in item["slot"])

    def test_some_bookings_exist(self):
        resource1 = ResourceFactory()
        resource2 = ResourceFactory()
        user = UserFactory()
        booking1 = BookingFactory(
            resource=resource1,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 5, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 9, 0)),
            ),
        )
        booking2 = BookingFactory(
            resource=resource1,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 18, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 5, 22, 0)),
            ),
        )
        booking3 = BookingFactory(
            resource=resource2,
            status=BookingStatus.CONFIRMED,
            timespan=(
                timezone.make_aware(timezone.datetime(2024, 6, 5, 23, 0)),
                timezone.make_aware(timezone.datetime(2024, 6, 6, 22, 0)),
            ),
        )
        booking1.save()
        booking2.save()
        booking3.save()

        date = timezone.make_aware(timezone.datetime(2024, 6, 5))

        date_string = date.strftime("%Y-%m-%d")
        resources, timeslots, dates = planner(user, date_string)

        number_of_timeslots = 48
        assert len(timeslots) == number_of_timeslots
        assert timeslots[16]["slot"][0] == {"booked": True, "booking_link": None}
        # This should be True because we booked the slot from 8:00 to 9:00
        assert timeslots[26]["slot"][0] == {
            "booked": False,
            "booking_link": "?starttime=13:00&endtime=14:30&startdate=2024-06-05"
            "&resource=" + resource1.slug,
        }  # This should be False because we did not book the slot
        assert timeslots[36]["slot"][0] == {"booked": True, "booking_link": None}
        assert timeslots[36]["slot"][1] == {
            "booked": False,
            "booking_link": "?starttime=18:00&endtime=19:30&startdate=2024-06-05"
            "&resource=" + resource2.slug,
        }  # This should be True because we booked the slot from 18:00 to 22:00


class TestGetUserAccessibleLocations(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.location1 = LocationFactory(name="Public Location")
        self.location2 = LocationFactory(name="Private Location")
        self.location3 = LocationFactory(name="Group Location")

        # Create public resource at location1
        self.public_resource = ResourceFactory(
            location=self.location1, is_private=False
        )

        # Create private resource at location2
        self.private_resource = ResourceFactory(
            location=self.location2, is_private=True
        )

        # Create group-accessible resource at location3
        self.group_resource = ResourceFactory(location=self.location3, is_private=True)

    def test_non_staff_user_sees_only_public_locations(self):
        accessible_locations = get_user_accessible_locations(self.user)
        location_names = {loc.name for loc in accessible_locations}

        assert "Public Location" in location_names
        assert "Private Location" not in location_names
        assert "Group Location" not in location_names

    def test_staff_user_sees_all_accessible_locations(self):
        from re_sharing.organizations.models import BookingPermission
        from re_sharing.organizations.tests.factories import BookingPermissionFactory
        from re_sharing.organizations.tests.factories import OrganizationFactory
        from re_sharing.organizations.tests.factories import OrganizationGroupFactory

        # Create organization and group structure
        organization = OrganizationFactory()
        organization_group = OrganizationGroupFactory()
        organization.organization_groups.add(organization_group)

        # Add user to organization
        BookingPermissionFactory(
            user=self.staff_user,
            organization=organization,
            status=BookingPermission.Status.CONFIRMED,
        )

        # Make group_resource accessible via organization group
        organization_group.bookable_private_resources.add(self.group_resource)

        accessible_locations = get_user_accessible_locations(self.staff_user)
        location_names = {loc.name for loc in accessible_locations}

        # Staff user should see public locations and group-accessible locations
        assert "Public Location" in location_names
        assert "Group Location" in location_names


class TestFilterResources(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.location = LocationFactory()

        # Create resources with different capacities
        self.small_resource = ResourceFactory(
            max_persons=2, location=self.location, is_private=False
        )
        self.medium_resource = ResourceFactory(
            max_persons=5, location=self.location, is_private=False
        )
        self.large_resource = ResourceFactory(
            max_persons=10, location=self.location, is_private=False
        )

    def test_filter_resources_by_location(self):
        # Create another location and resource
        other_location = LocationFactory()
        other_resource = ResourceFactory(location=other_location, is_private=False)

        resources = filter_resources(self.user, None, None, self.location.slug)

        # Should only include resources from specified location
        assert self.small_resource in resources
        assert self.medium_resource in resources
        assert self.large_resource in resources
        assert other_resource not in resources

    def test_filter_resources_excludes_booked_at_time(self):
        # Create a booking that overlaps with the specified time
        start_time = "2023-12-15T10:00"
        booking_start = timezone.make_aware(timezone.datetime(2023, 12, 15, 10, 15))
        booking_end = timezone.make_aware(timezone.datetime(2023, 12, 15, 11, 0))

        BookingFactory(
            resource=self.medium_resource,
            timespan=(booking_start, booking_end),
            status=BookingStatus.CONFIRMED,
        )

        resources = filter_resources(self.user, None, start_time, None)

        # Should exclude the booked resource
        assert self.small_resource in resources
        assert self.medium_resource not in resources
        assert self.large_resource in resources


class TestManagerAccessibleMethods(TestCase):
    """Test Manager model methods for accessing resources."""

    def setUp(self):
        from re_sharing.providers.tests.factories import ManagerFactory
        from re_sharing.users.tests.factories import UserFactory

        # Create a manager with specific resources
        self.manager_user = UserFactory()
        self.resource1 = ResourceFactory()
        self.resource2 = ResourceFactory()
        self.manager = ManagerFactory(
            user=self.manager_user, resources=[self.resource1, self.resource2]
        )

        # Create access codes for manager's resources
        self.access_code1 = AccessCodeFactory(access=self.resource1.access)
        self.access_code2 = AccessCodeFactory(access=self.resource2.access)

        # Create another resource and access code that manager doesn't have access to
        self.other_resource = ResourceFactory()
        self.other_access_code = AccessCodeFactory(access=self.other_resource.access)

    def test_get_accessible_access_ids(self):
        """Test that we get correct Access IDs for manager's resources."""
        accessible_ids = list(self.manager.get_accessible_access_ids())

        # Should include access IDs for manager's resources
        assert self.resource1.access.id in accessible_ids
        assert self.resource2.access.id in accessible_ids

        # Should NOT include other access IDs
        assert self.other_resource.access.id not in accessible_ids

    def test_get_accessible_accesses(self):
        """Test that we get correct Access objects for manager's resources."""
        accessible_accesses = self.manager.get_accessible_accesses()

        # Should include accesses for manager's resources
        assert self.resource1.access in accessible_accesses
        assert self.resource2.access in accessible_accesses

        # Should NOT include other accesses
        assert self.other_resource.access not in accessible_accesses

    def test_get_accessible_access_codes(self):
        """Test that we get correct AccessCodes for manager's resources."""
        accessible_codes = self.manager.get_accessible_access_codes()

        # Should include access codes for manager's resources
        assert self.access_code1 in accessible_codes
        assert self.access_code2 in accessible_codes

        # Should NOT include other access codes
        assert self.other_access_code not in accessible_codes

    def test_manager_with_no_resources(self):
        """Test that a manager with no resources gets empty results."""
        from re_sharing.providers.tests.factories import ManagerFactory
        from re_sharing.users.tests.factories import UserFactory

        empty_manager_user = UserFactory()
        empty_manager = ManagerFactory(user=empty_manager_user, resources=[])

        accessible_ids = list(empty_manager.get_accessible_access_ids())
        accessible_accesses = empty_manager.get_accessible_accesses()
        accessible_codes = empty_manager.get_accessible_access_codes()

        assert len(accessible_ids) == 0
        assert accessible_accesses.count() == 0
        assert accessible_codes.count() == 0

    def test_manager_with_duplicate_access_ids(self):
        """Test that duplicate Access IDs are properly deduplicated."""
        from re_sharing.providers.tests.factories import ManagerFactory
        from re_sharing.users.tests.factories import UserFactory

        # Create two resources with the same access
        same_access = AccessFactory()
        resource_a = ResourceFactory(access=same_access)
        resource_b = ResourceFactory(access=same_access)

        manager_user = UserFactory()
        manager = ManagerFactory(user=manager_user, resources=[resource_a, resource_b])

        accessible_ids = list(manager.get_accessible_access_ids())

        # Should only have one instance of the access ID (deduplicated)
        assert accessible_ids.count(same_access.id) == 1
        assert len(accessible_ids) == 1
