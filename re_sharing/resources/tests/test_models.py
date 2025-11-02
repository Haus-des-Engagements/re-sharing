from datetime import date
from datetime import datetime
from datetime import time

from django.test import TestCase
from django.utils import timezone

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.resources.tests.factories import ResourceRestrictionFactory


class ResourceRestrictionTest(TestCase):
    def setUp(self):
        self.resource = ResourceFactory()
        self.organization = OrganizationFactory()
        self.org_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(self.org_group)

    def test_applies_to_organization(self):
        # Create a restriction with no exempt organization groups
        restriction = ResourceRestrictionFactory(resources=[self.resource])

        # The restriction should apply to any organization
        assert restriction.applies_to_organization(self.organization)

        # Create a restriction with an exempt organization group
        exempt_restriction = ResourceRestrictionFactory(
            resources=[self.resource], exempt_organization_groups=[self.org_group]
        )

        # The restriction should not apply to an organization in the exempt group
        assert not exempt_restriction.applies_to_organization(self.organization)

        # Create another organization not in the exempt group
        other_organization = OrganizationFactory()

        # The restriction should apply to an organization not in the exempt group
        assert exempt_restriction.applies_to_organization(other_organization)

    def test_applies_to_datetime(self):
        # Create a restriction for weekdays (Monday-Friday) from 00:00 to 18:00
        restriction = ResourceRestrictionFactory(
            resources=[self.resource],
            start_time=time(0, 0),
            end_time=time(18, 0),
            days_of_week="0,1,2,3,4",  # Monday to Friday
        )

        # Test a datetime within the restriction (Monday at 12:00)
        monday_noon = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=5, day=5, hour=12, minute=0, second=0, microsecond=0
        )  # A Monday
        assert restriction.applies_to_datetime(monday_noon)

        # Test a datetime outside the restriction time (Monday at 19:00)
        monday_evening = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=5, day=5, hour=19, minute=0, second=0, microsecond=0
        )  # A Monday
        assert not restriction.applies_to_datetime(monday_evening)

        # Test a datetime outside the restriction days (Saturday at 12:00)
        saturday_noon = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=5, day=3, hour=12, minute=0, second=0, microsecond=0
        )  # A Saturday
        assert not restriction.applies_to_datetime(saturday_noon)

    def test_applies_to_datetime_with_date_range(self):
        """Test that restrictions respect the date range (start_date and end_date)."""
        # Create a restriction from 2025-05-01 to 2025-05-31
        restriction = ResourceRestrictionFactory(
            resources=[self.resource],
            start_time=time(0, 0),
            end_time=time(23, 59),
            days_of_week="0,1,2,3,4,5,6",  # All days
            start_date=date(2025, 5, 1),
            end_date=date(2025, 5, 31),
        )

        # Test datetime within the date range (May 15, 2025)
        within_range = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=5, day=15, hour=12, minute=0, second=0, microsecond=0
        )
        assert restriction.applies_to_datetime(within_range)

        # Test datetime before the date range (April 15, 2025)
        before_range = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=15, hour=12, minute=0, second=0, microsecond=0
        )
        assert not restriction.applies_to_datetime(before_range)

        # Test datetime after the date range (June 15, 2025)
        after_range = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=6, day=15, hour=12, minute=0, second=0, microsecond=0
        )
        assert not restriction.applies_to_datetime(after_range)

    def test_applies_to_datetime_with_only_start_date(self):
        """Test that restrictions with only start_date apply from that date onwards."""
        # Create a restriction starting from 2025-05-01 with no end date
        restriction = ResourceRestrictionFactory(
            resources=[self.resource],
            start_time=time(0, 0),
            end_time=time(23, 59),
            days_of_week="0,1,2,3,4,5,6",  # All days
            start_date=date(2025, 5, 1),
            end_date=None,
        )

        # Test datetime before start_date (April 15, 2025)
        before_start = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=15, hour=12, minute=0, second=0, microsecond=0
        )
        assert not restriction.applies_to_datetime(before_start)

        # Test datetime on start_date (May 1, 2025)
        on_start_date = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=5, day=1, hour=12, minute=0, second=0, microsecond=0
        )
        assert restriction.applies_to_datetime(on_start_date)

        # Test datetime after start_date (June 15, 2025)
        after_start = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=6, day=15, hour=12, minute=0, second=0, microsecond=0
        )
        assert restriction.applies_to_datetime(after_start)

    def test_applies_to_datetime_with_no_date_range(self):
        """
        Test that restrictions with no date range always apply.

        Based on time/days only.
        """
        # Create a restriction with no date range
        restriction = ResourceRestrictionFactory(
            resources=[self.resource],
            start_time=time(9, 0),
            end_time=time(17, 0),
            days_of_week="0,1,2,3,4",  # Weekdays
            start_date=None,
            end_date=None,
        )

        # Test datetime in the past (should apply if time and day match)
        past_weekday = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2020, month=1, day=6, hour=10, minute=0, second=0, microsecond=0
        )  # Monday
        assert restriction.applies_to_datetime(past_weekday)

        # Test datetime in the future (should apply if time and day match)
        future_weekday = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2030, month=1, day=7, hour=10, minute=0, second=0, microsecond=0
        )  # Monday
        assert restriction.applies_to_datetime(future_weekday)
