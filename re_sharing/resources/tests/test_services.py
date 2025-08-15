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
        # gets as access_code1, as there is no access_key having a specific organization
        assert (
            get_access_code(
                resource_slug=self.resource1.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=1)),
            )
            == self.access_code1
        )

        # we should still get back access_code1,
        # because access_code2 is only for organization2
        assert (
            get_access_code(
                resource_slug=self.resource1.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=10)),
            )
            == self.access_code1
        )

        # we should get back access_code2,
        # because access_code2 is only for organization2
        assert (
            get_access_code(
                resource_slug=self.resource1.slug,
                organization_slug=self.organization2.slug,
                timestamp=(self.timestamp + timedelta(days=10)),
            )
            == self.access_code2
        )

        assert (
            get_access_code(
                resource_slug=self.resource2.slug,
                organization_slug=self.organization1.slug,
                timestamp=(self.timestamp + timedelta(days=1)),
            )
            is None
        )


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
            resource=self.medium_resource, timespan=(booking_start, booking_end)
        )

        resources = filter_resources(self.user, None, start_time, None)

        # Should exclude the booked resource
        assert self.small_resource in resources
        assert self.medium_resource not in resources
        assert self.large_resource in resources
