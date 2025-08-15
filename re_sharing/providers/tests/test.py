from django.test import TestCase

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory


class ManagerFactoryTest(TestCase):
    """Test the ManagerFactory."""

    def test_manager_factory_creates_manager(self):
        """Test that ManagerFactory creates a Manager instance."""
        manager = ManagerFactory()
        assert manager is not None
        assert manager.user is not None

        assert manager.resources.count() == 0
        assert manager.organization_groups.count() == 0

    def test_manager_factory_with_resources(self):
        """Test that ManagerFactory creates a Manager with resources."""
        resource1 = ResourceFactory()
        resource2 = ResourceFactory()
        manager = ManagerFactory(resources=[resource1, resource2])

        assert manager.resources.count() == 2  # noqa: PLR2004
        assert resource1 in manager.resources.all()
        assert resource2 in manager.resources.all()

    def test_manager_factory_with_organization_groups(self):
        """Test that ManagerFactory creates a Manager with organization groups."""
        org_group1 = OrganizationGroupFactory()
        org_group2 = OrganizationGroupFactory()
        manager = ManagerFactory(organization_groups=[org_group1, org_group2])

        assert manager.organization_groups.count() == 2  # noqa: PLR2004
        assert org_group1 in manager.organization_groups.all()
        assert org_group2 in manager.organization_groups.all()


class TestManagerModel(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.manager = ManagerFactory(user=self.user)
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()

    def test_manager_str_representation(self):
        assert str(self.manager) == f"Manager: {self.user}"

    def test_can_manage_organization_no_groups(self):
        # Manager with no organization groups can manage any organization
        assert self.manager.can_manage_organization(self.organization)

    def test_can_manage_organization_with_groups(self):
        organization_group = OrganizationGroupFactory()
        self.manager.organization_groups.add(organization_group)
        self.organization.organization_groups.add(organization_group)

        # Manager should be able to manage organization in their group
        assert self.manager.can_manage_organization(self.organization)

    def test_cannot_manage_organization_different_group(self):
        organization_group1 = OrganizationGroupFactory()
        organization_group2 = OrganizationGroupFactory()

        self.manager.organization_groups.add(organization_group1)
        self.organization.organization_groups.add(organization_group2)

        # Manager should not be able to manage organization in different group
        assert not self.manager.can_manage_organization(self.organization)

    def test_can_manage_booking_success(self):
        organization_group = OrganizationGroupFactory()
        self.manager.organization_groups.add(organization_group)
        self.organization.organization_groups.add(organization_group)
        self.manager.resources.add(self.resource)

        booking = BookingFactory(organization=self.organization, resource=self.resource)

        assert self.manager.can_manage_booking(booking)

    def test_cannot_manage_booking_wrong_organization(self):
        organization_group1 = OrganizationGroupFactory()
        organization_group2 = OrganizationGroupFactory()

        self.manager.organization_groups.add(organization_group1)
        self.organization.organization_groups.add(organization_group2)
        self.manager.resources.add(self.resource)

        booking = BookingFactory(organization=self.organization, resource=self.resource)

        assert not self.manager.can_manage_booking(booking)

    def test_cannot_manage_booking_wrong_resource(self):
        organization_group = OrganizationGroupFactory()
        other_resource = ResourceFactory()

        self.manager.organization_groups.add(organization_group)
        self.organization.organization_groups.add(organization_group)
        self.manager.resources.add(other_resource)

        booking = BookingFactory(organization=self.organization, resource=self.resource)

        assert not self.manager.can_manage_booking(booking)

    def test_get_organizations_no_groups(self):
        organizations = self.manager.get_organizations()
        assert organizations.count() == 0

    def test_get_organizations_with_groups(self):
        organization_group = OrganizationGroupFactory()
        organization2 = OrganizationFactory()

        self.manager.organization_groups.add(organization_group)
        self.organization.organization_groups.add(organization_group)
        organization2.organization_groups.add(organization_group)

        organizations = self.manager.get_organizations()
        assert self.organization in organizations
        assert organization2 in organizations

    def test_get_resources(self):
        resource2 = ResourceFactory()

        self.manager.resources.add(self.resource)
        self.manager.resources.add(resource2)

        resources = self.manager.get_resources()
        assert self.resource in resources
        assert resource2 in resources
        assert resources.count() == 2  # noqa: PLR2004
