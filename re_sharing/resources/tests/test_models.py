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
