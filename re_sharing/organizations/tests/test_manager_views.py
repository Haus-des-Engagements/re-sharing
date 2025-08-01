from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.models import Manager
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus

User = get_user_model()


class ManagerOrganizationViewsTest(TestCase):
    def setUp(self):
        # Create users
        self.regular_user = UserFactory()
        self.manager_user = UserFactory()

        # Create organization groups
        self.group1 = OrganizationGroupFactory(name="Group 1")
        self.group2 = OrganizationGroupFactory(name="Group 2")

        # Create organizations
        self.org1 = OrganizationFactory(
            name="Organization 1",
            status=BookingStatus.PENDING,
        )
        self.org1.organization_groups.add(self.group1)

        self.org2 = OrganizationFactory(
            name="Organization 2",
            status=BookingStatus.PENDING,
        )
        self.org2.organization_groups.add(self.group2)

        # Create manager with access to group1
        self.manager = Manager.objects.create(user=self.manager_user)
        self.manager.organization_groups.add(self.group1)

    def test_regular_user_cannot_access_manager_list_view(self):
        """Test that regular users cannot access the manager list view"""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("organizations:manager-list-organizations"))
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_manager_can_access_manager_list_view(self):
        """Test that managers can access the manager list view"""
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse("organizations:manager-list-organizations"))
        assert response.status_code == HTTPStatus.OK

    def test_manager_only_sees_assigned_organizations(self):
        """Test that managers only see organizations from their assigned groups"""
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse("organizations:manager-list-organizations"))

        # Manager should see org1 (in group1) but not org2 (in group2)
        organizations = response.context["organizations"]
        assert self.org1 in organizations
        assert self.org2 not in organizations

    def test_manager_only_sees_assigned_groups_in_filter(self):
        """Test that managers only see their assigned groups in the filter dropdown"""
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse("organizations:manager-list-organizations"))

        # Manager should see group1 but not group2 in the filter dropdown
        groups = response.context["groups"]
        assert self.group1 in groups
        assert self.group2 not in groups

    def test_manager_with_no_groups_sees_all_organizations(self):
        """Test that managers with no assigned groups see all organizations"""
        # Remove the group assignment
        self.manager.organization_groups.clear()

        self.client.force_login(self.manager_user)
        response = self.client.get(reverse("organizations:manager-list-organizations"))

        # Manager should see both org1 and org2
        organizations = response.context["organizations"]
        assert self.org1 in organizations
        assert self.org2 in organizations

        # Manager should see all groups in the filter dropdown
        groups = response.context["groups"]
        assert len(groups) == 2  # Should see both groups # noqa: PLR2004
