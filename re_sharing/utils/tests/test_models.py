from django.test import TestCase

from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.users.tests.factories import UserGroupFactory
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import get_booking_status


class TestGetBookingStatus(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.superuser = UserFactory(is_superuser=True)
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.pending_organization = OrganizationFactory(
            status=Organization.Status.PENDING
        )
        self.resource = ResourceFactory()
        self.org_group = OrganizationGroupFactory()
        self.user_group = UserGroupFactory()

    def test_staff_user_gets_confirmed_status(self):
        # Staff users should always get CONFIRMED status
        status = get_booking_status(self.staff_user, self.organization, self.resource)
        assert status == BookingStatus.CONFIRMED

    def test_superuser_gets_confirmed_status(self):
        # Superusers should always get CONFIRMED status
        status = get_booking_status(self.superuser, self.organization, self.resource)
        assert status == BookingStatus.CONFIRMED

    def test_organization_in_auto_confirmed_group(self):
        # Add the resource to the organization group's auto_confirmed_resources
        self.org_group.auto_confirmed_resources.add(self.resource)
        # Add the organization to the organization group
        self.org_group.organizations_of_organizationgroups.add(self.organization)

        # The user should get CONFIRMED status because the organization is in a group
        # that has the resource in its auto_confirmed_resources
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.CONFIRMED

    def test_pending_organization_gets_pending_status(self):
        # Add the resource to the organization group's auto_confirmed_resources
        self.org_group.auto_confirmed_resources.add(self.resource)
        # Add the pending organization to the organization group
        self.org_group.organizations_of_organizationgroups.add(
            self.pending_organization
        )

        # The user should get PENDING status because the organization is pending
        status = get_booking_status(self.user, self.pending_organization, self.resource)
        assert status == BookingStatus.PENDING

    def test_user_in_auto_confirmed_group(self):
        # Add the resource to the user group's auto_confirmed_resources
        self.user_group.auto_confirmed_resources.add(self.resource)
        # Add the user to the user group
        self.user.usergroups_of_user.add(self.user_group)

        # The user should get CONFIRMED status because they are in a group
        # that has the resource in its auto_confirmed_resources
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.CONFIRMED

    def test_default_pending_status(self):
        # By default, users should get PENDING status
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.PENDING
