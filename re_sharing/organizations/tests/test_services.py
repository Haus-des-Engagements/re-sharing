from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.forms import OrganizationForm
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import InvalidOrganizationOperationError
from re_sharing.organizations.services import create_organization
from re_sharing.organizations.services import manager_cancel_organization
from re_sharing.organizations.services import manager_confirm_organization
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.organizations.services import show_organization
from re_sharing.organizations.services import user_has_admin_bookingpermission
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.organizations.services import user_has_normal_bookingpermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


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

    # Create organization groups - one default and one non-default
    default_group = OrganizationGroupFactory(
        default_group=True, show_on_organization_creation=True
    )
    non_default_group = OrganizationGroupFactory(default_group=False)

    # Create a dummy PDF file
    dummy_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type%%EOF"
    uploaded_file = SimpleUploadedFile(
        "test_usage_agreement.pdf", dummy_pdf_content, content_type="application/pdf"
    )

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
        "is_charitable": True,
        "values_approval": True,
        "usage_agreement_date": timezone.now().date(),
        "organization_groups": [default_group.id],
    }

    # For file uploads, we need to pass files separately from data
    form = OrganizationForm(
        data=form_data, files={"usage_agreement": uploaded_file}, user=test_user
    )

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

    # Check that the default group was assigned to the organization
    # Note: The current implementation overwrites the form selection with default groups
    # If this is a bug, the test should be updated after fixing the implementation
    org_groups = new_org.organization_groups.all()
    assert default_group in org_groups
    assert (
        non_default_group not in org_groups
    )  # This would fail if the implementation is fixed to add default
    # groups instead of replacing


@pytest.mark.django_db()
@patch("re_sharing.organizations.mails.organization_confirmation_email")
@patch.object(Organization, "is_confirmable", return_value=True)
def test_manager_confirm_organization(mock_is_confirmable, mock_send_email):
    user = UserFactory()
    organization = OrganizationFactory()
    organization = manager_confirm_organization(user, organization.slug)

    assert organization.status == BookingStatus.CONFIRMED

    mock_send_email.enqueue.assert_called_once_with(organization.id)


@pytest.mark.django_db()
@patch.object(Organization, "is_confirmable", return_value=False)
def test_manager_confirm_organization_not_confirmable(mock_is_confirmable):
    user = UserFactory()
    organization = OrganizationFactory()

    with pytest.raises(InvalidOrganizationOperationError):
        manager_confirm_organization(user, organization.slug)


@pytest.mark.django_db()
@patch.object(Organization, "is_cancelable", return_value=True)
def test_manager_cancel_organization(mock_is_cancelable):
    user = UserFactory()
    organization = OrganizationFactory()
    organization = manager_cancel_organization(user, organization.slug)

    assert organization.status == BookingStatus.CANCELLED


@pytest.mark.django_db()
@patch.object(Organization, "is_cancelable", return_value=False)
def test_manager_cancel_organization_not_cancelable(mock_is_cancelable):
    user = UserFactory()
    organization = OrganizationFactory()

    with pytest.raises(InvalidOrganizationOperationError):
        manager_cancel_organization(user, organization.slug)


class TestUserPermissionsFunctions(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.organization = OrganizationFactory()
        self.booking = BookingFactory(organization=self.organization)

    def test_user_has_bookingpermission_staff_user(self):
        # Staff users should always have booking permission
        assert user_has_bookingpermission(self.staff_user, self.booking)

    def test_user_has_bookingpermission_confirmed_user(self):
        # User with confirmed booking permission
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        assert user_has_bookingpermission(self.user, self.booking)

    def test_user_has_bookingpermission_pending_user(self):
        # User with pending booking permission should not have access
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.PENDING,
        )
        assert not user_has_bookingpermission(self.user, self.booking)

    def test_user_has_normal_bookingpermission(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        assert user_has_normal_bookingpermission(self.user, self.organization)

    def test_user_has_normal_bookingpermission_false(self):
        assert not user_has_normal_bookingpermission(self.user, self.organization)

    def test_organizations_with_confirmed_bookingpermission(self):
        organization2 = OrganizationFactory()

        # Give user confirmed permission for first org, pending for second
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        BookingPermissionFactory(
            user=self.user,
            organization=organization2,
            status=BookingPermission.Status.PENDING,
        )

        confirmed_orgs = organizations_with_confirmed_bookingpermission(self.user)
        assert self.organization in confirmed_orgs
        assert organization2 not in confirmed_orgs

    def test_user_has_admin_bookingpermission_manager(self):
        from re_sharing.providers.tests.factories import ManagerFactory

        manager_user = UserFactory()
        ManagerFactory(user=manager_user)
        assert user_has_admin_bookingpermission(manager_user, self.organization)

    def test_user_has_admin_bookingpermission_admin_role(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
            role=BookingPermission.Role.ADMIN,
        )
        assert user_has_admin_bookingpermission(self.user, self.organization)

    def test_user_has_admin_bookingpermission_booker_role(self):
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
            role=BookingPermission.Role.BOOKER,
        )
        assert not user_has_admin_bookingpermission(self.user, self.organization)


# Permission service tests moved to new test_services_business_logic.py
# Keep only integration and higher-level service tests here
