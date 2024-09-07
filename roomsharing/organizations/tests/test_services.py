from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.organizations.forms import OrganizationForm
from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.models import Organization
from roomsharing.organizations.services import create_organization
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


@pytest.mark.django_db()
def test_create_organization():
    # Create a test user
    test_user = UserFactory()

    # Mock form data
    form_data = {
        "name": "Test Organization",
        "description": "We are so great, I can't believe it...",
        "street_and_housenb": "Test Street 123",
        "zip_code": "12345",
        "city": "Test City",
        "legal_form": Organization.LegalForm.NO_LEGAL_FORM,
        "email": "test@hde.fr",
        "phone": "015839",
        "area_of_activity": Organization.ActivityArea.ENVIRONMENT_NATURE_ANIMALS,
        "entitled": True,
        "values_approval": True,
    }
    form = OrganizationForm(data=form_data)

    # Ensure form is valid
    assert form.is_valid(), form.errors

    # Call the create_organization function
    new_org = create_organization(test_user, form)

    # Check that the organization was created correctly
    assert Organization.objects.filter(name="Test Organization").exists()
    assert new_org.status == Organization.Status.PENDING

    # Check that the booking permission was created correctly
    booking_permission = BookingPermission.objects.get(
        user=test_user, organization=new_org
    )
    assert booking_permission.status == BookingPermission.Status.CONFIRMED
    assert booking_permission.role == BookingPermission.Role.ADMIN
