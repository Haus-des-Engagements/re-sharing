from django.test import TestCase

from roomsharing.organizations.models import Organization
from roomsharing.organizations.tests.factories import DefaultBookingStatusFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.utils.models import BookingStatus


def test_organization_get_absolute_url(organization: Organization):
    assert organization.get_absolute_url() == f"/organizations/{organization.slug}/"


class TestOrganizationDefaultBookingStatus(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.room = RoomFactory()

    def test_default_booking_status_exists(self):
        default_status = BookingStatus.CONFIRMED
        DefaultBookingStatusFactory(
            organization=self.organization, room=self.room, status=default_status
        )

        status = self.organization.default_booking_status(self.room)
        assert status == default_status

    def test_default_booking_status_does_not_exist(self):
        status = self.organization.default_booking_status(self.room)
        assert status == BookingStatus.PENDING
