from datetime import date
from decimal import Decimal
from http import HTTPStatus

import pytest
import tablib
from django.core import mail
from django.test import TestCase
from django.urls import NoReverseMatch
from django.urls import reverse

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import SepaMandate
from re_sharing.agreements.resources import AgreementResource
from re_sharing.agreements.resources import SepaMandateResource
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.users.tests.factories import UserFactory

AGREEMENT_HEADERS = [
    "id",
    "organization",
    "kind",
    "status",
    "amount",
    "start_date",
    "decided_at",
    "notes",
]
MANDATE_HEADERS = [
    "id",
    "agreement",
    "reference",
    "account_holder",
    "iban",
    "bic",
    "bank_name",
    "signed_on",
]


def _import(resource, headers, rows, *, dry_run=False):
    dataset = tablib.Dataset(*rows, headers=headers)
    return resource().import_data(dataset, dry_run=dry_run)


class AgreementImportTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)

    def _row(self, **overrides):
        row = {
            "id": "",
            "organization": self.organization.id,
            "kind": self.kind.slug,
            "status": Agreement.Status.ACTIVE,
            "amount": "60.00",
            "start_date": "2019-04-01",
            "decided_at": "2019-04-15",
            "notes": "From the paper list",
        }
        row.update(overrides)
        return [row[header] for header in AGREEMENT_HEADERS]

    def test_rows_become_active_agreements_without_side_effects(self):
        result = _import(AgreementResource, AGREEMENT_HEADERS, [self._row()])

        assert not result.has_errors()
        assert not result.has_validation_errors()
        agreement = Agreement.objects.get()
        assert agreement.status == Agreement.Status.ACTIVE
        assert agreement.amount == Decimal("60.00")
        assert agreement.start_date == date(2019, 4, 1)
        assert agreement.notes == "From the paper list"
        assert not agreement.collections_of_agreement.exists()
        assert agreement.permanent_code is None
        assert mail.outbox == []
        assert not self.organization.organization_groups.filter(
            id=self.kind.organization_group_id
        ).exists()

    def test_dry_run_saves_nothing(self):
        _import(AgreementResource, AGREEMENT_HEADERS, [self._row()], dry_run=True)

        assert not Agreement.objects.exists()

    # The admin previews every import as a dry run and only offers the
    # confirmation when no row has an error.
    def test_second_open_agreement_of_the_kind_is_refused(self):
        result = _import(
            AgreementResource,
            AGREEMENT_HEADERS,
            [self._row(), self._row()],
            dry_run=True,
        )

        assert result.has_validation_errors()
        assert not Agreement.objects.exists()

    def test_unknown_kind_is_an_error(self):
        result = _import(
            AgreementResource, AGREEMENT_HEADERS, [self._row(kind="x")], dry_run=True
        )

        assert result.has_validation_errors() or result.has_errors()
        assert not Agreement.objects.exists()

    def test_export_contains_organization_name(self):
        agreement = AgreementFactory(organization__name="Example e.V.")

        dataset = AgreementResource().export()

        assert dataset.dict[0]["organization_name"] == "Example e.V."
        assert str(dataset.dict[0]["id"]) == str(agreement.id)
        assert "signed_document" not in dataset.headers


class MandateImportTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(status=Agreement.Status.ACTIVE)

    def _row(self, **overrides):
        row = {
            "id": "",
            "agreement": self.agreement.id,
            "reference": "HDE-VM-008",
            "account_holder": "Example e.V.",
            "iban": "DE89 3704 0044 0532 0130 00",
            "bic": "COBADEFFXXX",
            "bank_name": "Example Bank",
            "signed_on": "2024-04-15",
        }
        row.update(overrides)
        return [row[header] for header in MANDATE_HEADERS]

    def test_paper_mandate_imported_without_file(self):
        result = _import(SepaMandateResource, MANDATE_HEADERS, [self._row()])

        assert not result.has_errors()
        assert not result.has_validation_errors()
        mandate = SepaMandate.objects.get()
        assert mandate.reference == "HDE-VM-008"
        assert mandate.iban == VALID_IBAN
        assert mandate.signed_on == date(2024, 4, 15)
        assert not mandate.signed_document
        assert not mandate.is_active

    def test_invalid_iban_refused(self):
        result = _import(
            SepaMandateResource,
            MANDATE_HEADERS,
            [self._row(iban="DE00123")],
            dry_run=True,
        )

        assert result.has_validation_errors()
        assert not SepaMandate.objects.exists()

    def test_duplicate_reference_refused(self):
        other = AgreementFactory(status=Agreement.Status.ACTIVE)
        rows = [self._row(), self._row(agreement=other.id)]

        result = _import(SepaMandateResource, MANDATE_HEADERS, rows, dry_run=True)

        assert result.has_validation_errors()
        assert not SepaMandate.objects.exists()

    def test_second_open_mandate_for_an_agreement_refused(self):
        rows = [self._row(), self._row(reference="HDE-VM-009")]

        result = _import(SepaMandateResource, MANDATE_HEADERS, rows, dry_run=True)

        assert result.has_validation_errors()
        assert not SepaMandate.objects.exists()

    def test_numbering_continues_after_imported_references(self):
        from re_sharing.agreements.services import generate_mandate_reference

        _import(SepaMandateResource, MANDATE_HEADERS, [self._row()])

        with self.settings(SEPA_MANDATE_REFERENCE_PREFIX="HDE-VM"):
            assert generate_mandate_reference() == "HDE-VM-009"


class ImportAdminTest(TestCase):
    def setUp(self):
        self.client.force_login(UserFactory(is_staff=True, is_superuser=True))

    def test_agreements_offer_import_and_export(self):
        assert (
            self.client.get(reverse("admin:agreements_agreement_import")).status_code
            == HTTPStatus.OK
        )
        assert (
            self.client.get(reverse("admin:agreements_agreement_export")).status_code
            == HTTPStatus.OK
        )

    def test_mandates_offer_import_only(self):
        assert (
            self.client.get(reverse("admin:agreements_sepamandate_import")).status_code
            == HTTPStatus.OK
        )
        with pytest.raises(NoReverseMatch):
            reverse("admin:agreements_sepamandate_export")


class AgreementExportLayoutImportTest(TestCase):
    def test_rows_in_the_export_layout_with_empty_columns_import(self):
        kind = MembershipKindFactory()
        organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        headers = AgreementResource().export().headers
        values = {
            "organization": organization.id,
            "kind": kind.slug,
            "status": Agreement.Status.ACTIVE,
            "amount": "60.00",
            "start_date": "2019-04-01",
        }
        row = [values.get(header, "") for header in headers]

        result = _import(AgreementResource, headers, [row])

        assert not result.has_errors(), result.base_errors
        assert not result.has_validation_errors(), result.invalid_rows
        agreement = Agreement.objects.get()
        assert agreement.details == {}
        assert agreement.deposit_amount is None
        assert agreement.end_date is None
