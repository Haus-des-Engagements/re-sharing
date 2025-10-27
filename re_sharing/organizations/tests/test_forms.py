from django.test import TestCase

from re_sharing.organizations.forms import OrganizationForm
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.users.tests.factories import UserFactory


class TestOrganizationFormGroupsField(TestCase):
    """Test that organization_groups field behaves correctly for different user types"""

    def setUp(self):
        # Create organization groups
        self.group_shown_on_creation = OrganizationGroupFactory(
            name="Public Group",
            show_on_organization_creation=True,
            show_on_organization_creation_wording="Join Public Group",
        )
        self.group_not_shown_on_creation = OrganizationGroupFactory(
            name="Private Group",
            show_on_organization_creation=False,
        )
        self.manager_only_group = OrganizationGroupFactory(
            name="Manager Group",
            show_on_organization_creation=False,
        )

        # Create a regular user (organization admin)
        self.regular_user = UserFactory()

        # Create a manager user
        self.manager_user = UserFactory()
        self.manager = ManagerFactory(
            user=self.manager_user,
            organization_groups=[self.manager_only_group],
        )

    def test_non_manager_create_form_shows_public_groups_only(self):
        """
        Non-managers creating an organization see only
        show_on_organization_creation groups
        """
        form = OrganizationForm(user=self.regular_user)

        assert "organization_groups" in form.fields
        queryset = form.fields["organization_groups"].queryset
        assert self.group_shown_on_creation in queryset
        assert self.group_not_shown_on_creation not in queryset
        assert self.manager_only_group not in queryset

    def test_non_manager_edit_form_hides_organization_groups_field(self):
        """
        Non-managers editing an organization should not see
        organization_groups field
        """
        organization = OrganizationFactory()
        organization.organization_groups.add(
            self.group_shown_on_creation,
            self.group_not_shown_on_creation,
        )

        # Create admin permission for the user
        BookingPermissionFactory(
            user=self.regular_user,
            organization=organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

        form = OrganizationForm(user=self.regular_user, instance=organization)

        # organization_groups field should not be in the form
        assert "organization_groups" not in form.fields

    def test_manager_create_form_shows_public_and_manager_groups(self):
        """
        Managers creating an organization see public groups AND their
        assigned groups
        """
        form = OrganizationForm(user=self.manager_user)

        assert "organization_groups" in form.fields
        queryset = form.fields["organization_groups"].queryset
        assert self.group_shown_on_creation in queryset
        assert self.manager_only_group in queryset
        assert self.group_not_shown_on_creation not in queryset

    def test_manager_edit_form_shows_public_and_manager_groups(self):
        """
        Managers editing an organization can still see and modify
        organization_groups
        """
        organization = OrganizationFactory()
        organization.organization_groups.add(self.group_not_shown_on_creation)

        form = OrganizationForm(user=self.manager_user, instance=organization)

        # organization_groups field should be present
        assert "organization_groups" in form.fields
        queryset = form.fields["organization_groups"].queryset
        assert self.group_shown_on_creation in queryset
        assert self.manager_only_group in queryset
        assert self.group_not_shown_on_creation not in queryset

    def test_non_manager_edit_preserves_organization_groups(self):
        """
        Verify that when a non-manager edits an organization,
        the existing organization_groups are preserved
        """
        organization = OrganizationFactory()
        organization.organization_groups.add(
            self.group_shown_on_creation,
            self.group_not_shown_on_creation,
        )

        # Create admin permission for the user
        BookingPermissionFactory(
            user=self.regular_user,
            organization=organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

        # Initial groups
        initial_groups = set(organization.organization_groups.all())
        expected_groups = {
            self.group_shown_on_creation,
            self.group_not_shown_on_creation,
        }
        assert initial_groups == expected_groups

        # Create form (simulating edit)
        form = OrganizationForm(user=self.regular_user, instance=organization)

        # organization_groups should not be in the form
        assert "organization_groups" not in form.fields

        # The groups should remain unchanged in the database
        current_groups = set(organization.organization_groups.all())
        assert initial_groups == current_groups
