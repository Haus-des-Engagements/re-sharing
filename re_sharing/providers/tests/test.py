from django.test import TestCase

from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.tests.factories import ResourceFactory


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
