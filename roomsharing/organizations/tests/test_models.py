from django.test import TestCase

from roomsharing.organizations.models import Organization
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.organizations.tests.factories import OrganizationGroupFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.utils.models import BookingStatus


def test_organization_get_absolute_url(organization: Organization):
    assert organization.get_absolute_url() == f"/organizations/{organization.slug}/"


class TestOrganizationGetBookingStatus(TestCase):
    def setUp(self):
        self.room = RoomFactory()
        self.organization_group = OrganizationGroupFactory()
        self.organization_group.auto_confirmed_rooms.add(self.room)
        self.organization = OrganizationFactory()

    def test_default_booking_status_exists(self):
        self.organization.organization_groups.add(self.organization_group)
        status = self.organization.get_booking_status(self.room)
        assert status == BookingStatus.CONFIRMED

    def test_default_booking_status_does_not_exist(self):
        status = self.organization.get_booking_status(self.room)
        assert status == BookingStatus.PENDING
