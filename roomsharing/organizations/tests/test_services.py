from unittest.mock import patch

from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.services import show_organization
from roomsharing.organizations.tests.factories import BookingPermissionFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.users.tests.factories import UserFactory


class ShowOrganizationTest(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.organization = OrganizationFactory()
        self.show_organization_url = reverse(
            "organizations:show-organization",
            kwargs={"organization": self.organization.slug},
        )
        self.user = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()

    def test_access_user_is_not_authenticated(self):
        BookingPermissionFactory(
            user=self.user2,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
        )
        BookingPermissionFactory(
            user=self.user3,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
        )

        organization, permitted_users, is_admin = show_organization(
            self.user, self.organization.slug
        )
        assert is_admin is False
        assert permitted_users is None

    @patch("django.contrib.auth.models.User.is_authenticated", return_value=True)
    def test_access_user_is_member(self, _):  # noqa: PT019
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
        )
        BookingPermissionFactory(
            user=self.user2,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
        )

        organization, permitted_users, is_admin = show_organization(
            self.user, self.organization.slug
        )
        assert is_admin is False
        assert set(permitted_users) == {self.user, self.user2}

    @patch("django.contrib.auth.models.User.is_authenticated", return_value=True)
    def test_access_user_is_admin(self, _):  # noqa: PT019
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            role=BookingPermission.Role.BOOKER,
        )
        BookingPermissionFactory(
            user=self.user2,
            organization=self.organization,
            role=BookingPermission.Role.ADMIN,
        )

        organization, permitted_users, is_admin = show_organization(
            self.user2, self.organization.slug
        )
        assert is_admin is True
        assert set(permitted_users) == {self.user, self.user2}
