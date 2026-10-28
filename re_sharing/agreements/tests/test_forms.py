from datetime import date
from decimal import Decimal

from django.test import TestCase

from re_sharing.agreements.forms import ApplicationForm
from re_sharing.agreements.forms import ManagerAgreementEditForm
from re_sharing.agreements.forms import ManagerAgreementForm
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import AgreementKindField
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import AgreementKindFieldFactory
from re_sharing.agreements.tests.factories import CoworkingKindFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory

BASE = {"start_date": "2027-03-01", "amount": "120", "contact_person_function": "Chair"}


class ApplicationFormTest(TestCase):
    def test_kind_without_fields(self):
        kind = MembershipKindFactory()
        form = ApplicationForm(data=BASE, kind=kind)

        assert form.is_valid(), form.errors
        assert form.details() == {}
        assert "deposit_amount" not in form.fields
        assert "end_date" not in form.fields
        assert "yearly" in str(form.fields["amount"].help_text)

    def test_coworking_requires_details_and_deposit(self):
        kind = CoworkingKindFactory(requires_deposit=True)

        form = ApplicationForm(data=BASE, kind=kind)
        assert not form.is_valid()
        assert {"desks", "hours_per_week", "deposit_amount"} <= set(form.errors)

        form = ApplicationForm(
            data={
                **BASE,
                "desks": "2",
                "hours_per_week": "10",
                "deposit_amount": "360",
            },
            kind=kind,
        )
        assert form.is_valid(), form.errors
        assert form.details() == {"desks": 2, "hours_per_week": 10}
        assert form.cleaned_data["deposit_amount"] == Decimal(360)

    def test_minimum_enforced(self):
        kind = CoworkingKindFactory()

        form = ApplicationForm(
            data={**BASE, "desks": "0", "hours_per_week": "10"}, kind=kind
        )

        assert "desks" in form.errors

    def test_type_validated(self):
        kind = CoworkingKindFactory()

        form = ApplicationForm(
            data={**BASE, "desks": "abc", "hours_per_week": "10"}, kind=kind
        )

        assert "desks" in form.errors

    def test_end_date_required_and_after_start(self):
        kind = AgreementKindFactory(requires_end_date=True)

        assert "end_date" in ApplicationForm(data=BASE, kind=kind).errors
        form = ApplicationForm(data={**BASE, "end_date": "2027-02-01"}, kind=kind)
        assert "end_date" in form.errors

        form = ApplicationForm(data={**BASE, "end_date": "2029-02-28"}, kind=kind)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["end_date"] == date(2029, 2, 28)

    def test_detail_fields_follow_core_fields(self):
        kind = CoworkingKindFactory()

        names = list(ApplicationForm(kind=kind).fields)

        assert names.index("desks") > names.index("contact_person_function")
        assert names.index("hours_per_week") < names.index("signed_document")

    def test_amount_must_be_positive(self):
        form = ApplicationForm(
            data={**BASE, "amount": "0"}, kind=MembershipKindFactory()
        )

        assert "amount" in form.errors

    def test_signed_document_optional_but_with_date(self):
        form = ApplicationForm(
            data=BASE,
            files={"signed_document": pdf_file()},
            kind=MembershipKindFactory(),
        )

        assert "signed_on" in form.errors


class ManagerAgreementFormTest(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.kind = MembershipKindFactory()

    def test_offers_only_confirmed_organizations(self):
        pending = OrganizationFactory(status=Organization.Status.PENDING)

        queryset = ManagerAgreementForm(kind=self.kind).fields["organization"].queryset

        assert self.organization in queryset
        assert pending not in queryset

    def test_valid_without_contact_function(self):
        form = ManagerAgreementForm(
            data={
                "organization": self.organization.id,
                "status": Agreement.Status.ACTIVE,
                "decided_at": "2026-03-01",
                "start_date": "2026-01-01",
                "amount": "60",
                "notes": "Paper mandate",
            },
            kind=self.kind,
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["status"] == Agreement.Status.ACTIVE
        assert list(form.fields)[:3] == ["organization", "status", "decided_at"]
        assert list(form.fields)[-1] == "notes"

    def test_status_limited_to_submitted_and_active(self):
        form = ManagerAgreementForm(
            data={
                "organization": self.organization.id,
                "status": Agreement.Status.ENDED,
                "start_date": "2026-01-01",
                "amount": "60",
            },
            kind=self.kind,
        )

        assert "status" in form.errors


class ManagerAgreementEditFormTest(TestCase):
    def test_prefilled_from_agreement(self):
        kind = CoworkingKindFactory()
        agreement = AgreementFactory(
            kind=kind,
            details={"desks": 2, "hours_per_week": 10},
            notes="Note",
        )

        form = ManagerAgreementEditForm(agreement=agreement)

        assert form.initial["amount"] == agreement.amount
        assert form.initial["notes"] == "Note"
        assert form.fields["desks"].initial == 2  # noqa: PLR2004
        assert "signed_document" not in form.fields
        assert "status" not in form.fields

    def test_removed_choice_kept(self):
        kind = AgreementKindFactory()
        AgreementKindFieldFactory(
            kind=kind,
            key="size",
            field_type=AgreementKindField.FieldType.CHOICE,
            choices="small\nlarge",
        )
        agreement = AgreementFactory(kind=kind, details={"size": "medium"})

        form = ManagerAgreementEditForm(
            data={**BASE, "size": "medium"}, agreement=agreement
        )

        assert form.is_valid(), form.errors
        assert form.details() == {"size": "medium"}
