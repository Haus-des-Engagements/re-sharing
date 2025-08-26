from django.test import TestCase

from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import get_booking_status


class TestGetBookingStatus(TestCase):
    def setUp(self):
        self.resource = ResourceFactory()
        self.organization_group = OrganizationGroupFactory()
        self.organization = OrganizationFactory()
        self.user = UserFactory()

    def test_pending_by_not_confirmed_organization(self):
        self.organization.organization_groups.add(self.organization_group)
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.PENDING

    def test_confirmed_by_confirmed_organization(self):
        self.organization.status = Organization.Status.CONFIRMED
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.PENDING

    def test_confirmed_by_confirmed_organization_with_autoconfirm(self):
        self.organization.organization_groups.add(self.organization_group)
        self.organization_group.auto_confirmed_resources.add(self.resource)
        self.organization.status = Organization.Status.CONFIRMED
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.CONFIRMED

    def test_pending_by_organization(self):
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.PENDING

    def test_confirmed_by_is_manager(self):
        manager = ManagerFactory(user=self.user)
        self.organization.organization_groups.add(self.organization_group)
        manager.organization_groups.add(self.organization_group)
        manager.resources.add(self.resource)
        status = get_booking_status(self.user, self.organization, self.resource)
        assert status == BookingStatus.CONFIRMED
