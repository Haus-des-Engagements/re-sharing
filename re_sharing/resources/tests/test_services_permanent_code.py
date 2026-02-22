"""Tests for permanent code service functions."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.models import PermanentCode
from re_sharing.resources.services_permanent_code import (
    create_permanent_code_for_organization,
)
from re_sharing.resources.services_permanent_code import invalidate_permanent_code
from re_sharing.resources.services_permanent_code import renew_permanent_code
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import PermanentCodeFactory
from re_sharing.users.tests.factories import UserFactory


class TestCreatePermanentCode(TestCase):
    """Test creating permanent codes for organizations."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        # Create accesses 1, 2, 8 as required by the service
        self.access1 = AccessFactory(id=1)
        self.access2 = AccessFactory(id=2)
        self.access8 = AccessFactory(id=8)

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    @patch(
        "re_sharing.resources.services_permanent_code.send_permanent_code_created_email"
    )
    def test_create_permanent_code_success(self, mock_email, mock_generate_code):
        """Test successful permanent code creation."""
        mock_generate_code.return_value = "123456"

        permanent_code = create_permanent_code_for_organization(
            self.organization.slug, self.user
        )

        # Verify code was created
        assert permanent_code.code == "123456"
        assert permanent_code.organization == self.organization
        assert permanent_code.validity_start is not None
        assert permanent_code.validity_end is None
        assert permanent_code.name == f"Permanent code for {self.organization.name}"

        # Verify accesses were set correctly
        access_ids = set(permanent_code.accesses.values_list("id", flat=True))
        assert access_ids == {1, 2, 8}

        # Verify email was queued
        mock_email.enqueue.assert_called_once_with(permanent_code.id)

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    def test_create_permanent_code_fails_when_active_code_exists(
        self, mock_generate_code
    ):
        """Test that creating a code fails when an active code exists."""
        # Create an existing active permanent code
        PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        # Attempt to create another code should fail
        with pytest.raises(ValidationError) as context:
            create_permanent_code_for_organization(self.organization.slug, self.user)

        assert "already has an active permanent code" in str(context.value)

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    def test_create_permanent_code_succeeds_when_previous_code_expired(
        self, mock_generate_code
    ):
        """Test that creating a code succeeds when previous code is expired."""
        mock_generate_code.return_value = "234567"

        # Create an expired permanent code
        PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=10),
            validity_end=timezone.now() - timedelta(days=1),
            accesses=[self.access1],
        )

        # Creating a new code should succeed
        permanent_code = create_permanent_code_for_organization(
            self.organization.slug, self.user
        )

        assert permanent_code.code == "234567"
        assert permanent_code.organization == self.organization


class TestInvalidatePermanentCode(TestCase):
    """Test invalidating permanent codes."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.access1 = AccessFactory()
        self.permanent_code = PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

    @patch("re_sharing.organizations.mails.send_permanent_code_invalidated_email")
    def test_invalidate_permanent_code_with_datetime(self, mock_email):
        """Test invalidating a code with a specific datetime."""
        validity_end = timezone.now() + timedelta(days=7)

        updated_code = invalidate_permanent_code(
            self.permanent_code.id, validity_end, self.user
        )

        assert updated_code.validity_end == validity_end
        assert updated_code.id == self.permanent_code.id

        # Verify email was queued
        mock_email.enqueue.assert_called_once_with(self.permanent_code.id)

    @patch("re_sharing.organizations.mails.send_permanent_code_invalidated_email")
    def test_invalidate_permanent_code_immediately(self, mock_email):
        """Test invalidating a code immediately."""
        validity_end = timezone.now()

        updated_code = invalidate_permanent_code(
            self.permanent_code.id, validity_end, self.user
        )

        assert updated_code.validity_end == validity_end

        # Verify email was queued
        mock_email.enqueue.assert_called_once_with(self.permanent_code.id)


class TestRenewPermanentCode(TestCase):
    """Test renewing permanent codes."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.user = UserFactory()
        self.access1 = AccessFactory()
        self.access2 = AccessFactory()
        self.old_code = PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=30),
            validity_end=None,
            accesses=[self.access1, self.access2],
        )

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    @patch(
        "re_sharing.resources.services_permanent_code.send_permanent_code_renewed_email"
    )
    def test_renew_permanent_code_success(self, mock_email, mock_generate_code):
        """Test successful permanent code renewal."""
        mock_generate_code.return_value = "987654"

        old_code, new_code = renew_permanent_code(self.old_code.id, self.user)

        # Verify old code was updated to expire in 1 week
        old_code.refresh_from_db()
        expected_expiry = timezone.now() + timedelta(weeks=1)
        assert old_code.validity_end is not None
        # Allow 1 second tolerance for time differences
        assert abs((old_code.validity_end - expected_expiry).total_seconds()) < 1

        # Verify new code was created
        assert new_code.code == "987654"
        assert new_code.organization == self.organization
        assert new_code.validity_start is not None
        assert new_code.validity_end is None
        assert new_code.name == f"Renewed permanent code for {self.organization.name}"

        # Verify accesses were copied
        old_access_ids = set(old_code.accesses.values_list("id", flat=True))
        new_access_ids = set(new_code.accesses.values_list("id", flat=True))
        assert old_access_ids == new_access_ids

        # Verify email was queued
        mock_email.enqueue.assert_called_once_with(new_code.id, old_code.id)

    @patch("re_sharing.resources.services_permanent_code._generate_permanent_code")
    def test_renew_creates_two_active_codes_temporarily(self, mock_generate_code):
        """Test that renewal creates a period where both codes are active."""
        mock_generate_code.return_value = "111111"

        old_code, new_code = renew_permanent_code(self.old_code.id, self.user)

        old_code.refresh_from_db()

        # Both codes should be active now
        now = timezone.now()
        assert old_code.validity_start <= now
        assert old_code.validity_end > now

        assert new_code.validity_start <= now
        assert new_code.validity_end is None


class TestCodeGeneration(TestCase):
    """Test code generation function."""

    @patch("random.choices")
    def test_generate_permanent_code_format(self, mock_random):
        """Test that generated codes follow the expected format."""
        from re_sharing.resources.services_permanent_code import (
            _generate_permanent_code,
        )

        # Mock to return a valid code (not starting with 12, no zeros)
        mock_random.return_value = ["3", "4", "5", "6", "7", "8"]

        code = _generate_permanent_code()

        assert len(code) == 6  # noqa: PLR2004
        assert code == "345678"
        assert not code.startswith("12")
        assert "0" not in code

    @patch("random.choices")
    def test_generate_permanent_code_rejects_code_starting_with_12(self, mock_random):
        """Test that codes starting with 12 are regenerated."""
        from re_sharing.resources.services_permanent_code import (
            _generate_permanent_code,
        )

        # First call returns invalid code starting with 12, second call returns valid
        mock_random.side_effect = [
            ["1", "2", "3", "4", "5", "6"],  # Invalid
            ["3", "4", "5", "6", "7", "8"],  # Valid
        ]

        code = _generate_permanent_code()

        assert code == "345678"
        assert mock_random.call_count == 2  # noqa: PLR2004


class TestPermanentCodeQuerySet(TestCase):
    """Test querying permanent codes."""

    def setUp(self):
        self.organization = OrganizationFactory()
        self.access1 = AccessFactory()

    def test_filter_active_permanent_codes(self):
        """Test filtering for currently active permanent codes."""
        # Create active code
        active_code = PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        # Create expired code
        PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() - timedelta(days=10),
            validity_end=timezone.now() - timedelta(days=1),
            accesses=[self.access1],
        )

        # Create future code
        PermanentCodeFactory(
            organization=self.organization,
            validity_start=timezone.now() + timedelta(days=1),
            validity_end=None,
            accesses=[self.access1],
        )

        # Query for active codes
        from django.db.models import Q

        active_codes = (
            PermanentCode.objects.filter(organization=self.organization)
            .filter(validity_start__lte=timezone.now())
            .filter(Q(validity_end__isnull=True) | Q(validity_end__gte=timezone.now()))
        )

        assert active_codes.count() == 1
        assert active_codes.first().id == active_code.id
