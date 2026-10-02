from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction

from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationGroupFactory


def test_organization_get_absolute_url(organization: Organization):
    assert organization.get_absolute_url() == f"/organizations/{organization.slug}/"


def test_is_deactivatable_only_when_confirmed(organization: Organization):
    organization.status = Organization.Status.CONFIRMED
    assert organization.is_deactivatable() is True

    organization.status = Organization.Status.PENDING
    assert organization.is_deactivatable() is False

    organization.status = Organization.Status.REJECTED
    assert organization.is_deactivatable() is False

    organization.status = Organization.Status.DEACTIVATED
    assert organization.is_deactivatable() is False


def test_is_activatable_only_when_deactivated(organization: Organization):
    organization.status = Organization.Status.DEACTIVATED
    assert organization.is_activatable() is True

    organization.status = Organization.Status.CONFIRMED
    assert organization.is_activatable() is False

    organization.status = Organization.Status.PENDING
    assert organization.is_activatable() is False

    organization.status = Organization.Status.REJECTED
    assert organization.is_activatable() is False


class TestOrganizationGroupFreeBookings:
    def test_defaults_are_unlimited(self, db):
        group = OrganizationGroupFactory()

        assert group.free_bookings_per_year is None
        assert group.free_bookings_valid_from is None

    def test_number_without_date_fails_validation(self, db):
        group = OrganizationGroupFactory.build(free_bookings_per_year=5)

        with pytest.raises(ValidationError) as excinfo:
            group.full_clean()

        assert "free_bookings_valid_from" in excinfo.value.error_dict

    def test_date_without_number_fails_validation(self, db):
        group = OrganizationGroupFactory.build(
            free_bookings_valid_from=date(2027, 1, 1)
        )

        with pytest.raises(ValidationError) as excinfo:
            group.full_clean()

        assert "free_bookings_per_year" in excinfo.value.error_dict

    def test_both_fields_set_pass_validation(self, db):
        group = OrganizationGroupFactory.build(
            free_bookings_per_year=5, free_bookings_valid_from=date(2027, 1, 1)
        )

        group.full_clean()
        group.save()

        assert group.free_bookings_per_year == 5  # noqa: PLR2004

    def test_number_without_date_is_rejected_by_the_database(self, db):
        with pytest.raises(IntegrityError), transaction.atomic():
            OrganizationGroupFactory(free_bookings_per_year=5)

    def test_date_without_number_is_rejected_by_the_database(self, db):
        with pytest.raises(IntegrityError), transaction.atomic():
            OrganizationGroupFactory(free_bookings_valid_from=date(2027, 1, 1))
