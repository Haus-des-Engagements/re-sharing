from datetime import date
from decimal import Decimal

from django.test import TestCase

from re_sharing.agreements.forms import CellarApplicationForm
from re_sharing.agreements.forms import CoworkingApplicationForm
from re_sharing.agreements.forms import MembershipApplicationForm
from re_sharing.agreements.forms import OfficeApplicationForm
from re_sharing.agreements.forms import application_form_class
from re_sharing.agreements.forms import detail_items
from re_sharing.agreements.models import AgreementKind
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import pdf_file

BASE = {"start_date": "2027-03-01", "amount": "120", "contact_person_function": "Chair"}


class ApplicationFormTest(TestCase):
    def test_form_class_per_kind(self):
        expected = {
            AgreementKind.FormType.MEMBERSHIP: MembershipApplicationForm,
            AgreementKind.FormType.COWORKING: CoworkingApplicationForm,
            AgreementKind.FormType.OFFICE: OfficeApplicationForm,
            AgreementKind.FormType.CELLAR: CellarApplicationForm,
        }
        for form_type, form_class in expected.items():
            kind = AgreementKindFactory.build(form_type=form_type)
            assert application_form_class(kind) is form_class

    def test_membership(self):
        kind = MembershipKindFactory()
        form = MembershipApplicationForm(data=BASE, kind=kind)

        assert form.is_valid(), form.errors
        assert form.details() == {}
        assert "deposit_amount" not in form.fields
        assert "end_date" not in form.fields
        assert "yearly" in str(form.fields["amount"].help_text)

    def test_coworking_requires_details_and_deposit(self):
        kind = AgreementKindFactory(requires_deposit=True)

        form = CoworkingApplicationForm(data=BASE, kind=kind)
        assert not form.is_valid()
        assert {"desks", "hours_per_week", "deposit_amount"} <= set(form.errors)

        form = CoworkingApplicationForm(
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

    def test_office_requires_end_date_after_start(self):
        kind = AgreementKindFactory(
            form_type=AgreementKind.FormType.OFFICE, requires_end_date=True
        )

        form = OfficeApplicationForm(data={**BASE, "room": "2.01"}, kind=kind)
        assert "end_date" in form.errors

        form = OfficeApplicationForm(
            data={**BASE, "room": "2.01", "end_date": "2027-02-01"}, kind=kind
        )
        assert "end_date" in form.errors

        form = OfficeApplicationForm(
            data={**BASE, "room": "2.01", "end_date": "2029-02-28"}, kind=kind
        )
        assert form.is_valid(), form.errors
        assert form.details() == {"room": "2.01"}
        assert form.cleaned_data["end_date"] == date(2029, 2, 28)

    def test_cellar_area_stored_as_string(self):
        kind = AgreementKindFactory(form_type=AgreementKind.FormType.CELLAR)
        form = CellarApplicationForm(data={**BASE, "area_m2": "12.5"}, kind=kind)

        assert form.is_valid(), form.errors
        assert form.details() == {"area_m2": "12.5"}

    def test_amount_must_be_positive(self):
        form = MembershipApplicationForm(
            data={**BASE, "amount": "0"}, kind=MembershipKindFactory()
        )

        assert "amount" in form.errors

    def test_signed_document_optional_but_with_date(self):
        form = MembershipApplicationForm(
            data=BASE,
            files={"signed_document": pdf_file()},
            kind=MembershipKindFactory(),
        )

        assert "signed_on" in form.errors

    def test_detail_items_use_form_labels(self):
        agreement = AgreementFactory(details={"desks": 2, "hours_per_week": 10})

        assert detail_items(agreement) == [("Desks", 2), ("Hours per week", 10)]
