from datetime import date
from decimal import Decimal
from http import HTTPStatus
from io import BytesIO

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from pypdf import PdfReader

from re_sharing.agreements import documents
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import AgreementKindField
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFieldFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import fillable_pdf
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_booker
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.users.tests.factories import UserFactory

TEXT_FIELDS = (
    "organization_name",
    "organization_address",
    "organization_phone",
    "organization_email",
    "organization_website",
    "representative_name",
    "representative_function",
    "representative_email",
    "amount",
    "start_date",
    "detail_area",
    "detail_since",
    "place_date",
)

CREDITOR = {
    "SEPA_CREDITOR_NAME": "Example Creditor e.V.",
    "SEPA_CREDITOR_ADDRESS": "Example Street 1, 12345 Example City",
    "SEPA_CREDITOR_ID": "DE98ZZZ09999999999",
}


def _kind_with_template():
    kind = MembershipKindFactory(
        contract_template=fillable_pdf(TEXT_FIELDS, ["represented_by_person"])
    )
    AgreementKindFieldFactory(
        kind=kind, key="area", field_type=AgreementKindField.FieldType.DECIMAL
    )
    AgreementKindFieldFactory(
        kind=kind, key="since", field_type=AgreementKindField.FieldType.DATE
    )
    return kind


def _values(content):
    return {
        name: field.get("/V")
        for name, field in (PdfReader(BytesIO(content)).get_fields() or {}).items()
    }


class FormattingTest(TestCase):
    def test_money_and_date(self):
        assert documents.format_money(Decimal("1234.5")) == "1.234,50"
        assert documents.format_money(None) == ""
        assert documents.format_date(date(2027, 3, 1)) == "01.03.2027"
        assert documents.format_date(None) == ""


class PrefilledContractTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template()
        self.person = UserFactory(first_name="Erika", last_name="Muster")
        self.agreement = AgreementFactory(
            kind=self.kind,
            amount=Decimal(80),
            contact_person=self.person,
            contact_person_function="Chair",
            details={"area": "12.5", "since": "2026-05-01"},
        )

    def test_template_field_names(self):
        names = documents.template_field_names(self.kind)

        assert names[0] == "organization_name"
        assert "represented_by_person" in names
        assert documents.template_field_names(MembershipKindFactory()) == []

    def test_fields_filled_by_name(self):
        organization = self.agreement.organization

        values = _values(documents.prefilled_contract(self.agreement, self.person))

        assert values["organization_name"] == organization.name
        assert values["organization_address"] == (
            f"{organization.street_and_housenb}, {organization.zip_code} "
            f"{organization.city}"
        )
        assert values["organization_email"] == organization.email
        assert values["representative_name"] == "Erika Muster"
        assert values["representative_function"] == "Chair"
        assert values["representative_email"] == self.person.email
        assert values["amount"] == "80,00"
        assert values["start_date"] == "01.03.2027"
        assert values["detail_area"] == "12,5"
        assert values["detail_since"] == "01.05.2026"
        assert values["represented_by_person"] != "/Off"
        assert values["place_date"] in (None, "")

    def test_fields_stay_editable(self):
        reader = PdfReader(
            BytesIO(documents.prefilled_contract(self.agreement, self.person))
        )

        assert reader.trailer["/Root"]["/AcroForm"]["/NeedAppearances"]
        for field in reader.get_fields().values():
            assert not int(field.get("/Ff", 0)) & 1  # not read-only

    def test_without_person(self):
        values = _values(documents.prefilled_contract(self.agreement, None))

        assert values["representative_name"] in (None, "")

    def test_is_filled_field(self):
        assert documents.is_filled_field(self.kind, "amount")
        assert documents.is_filled_field(self.kind, "detail_area")
        assert not documents.is_filled_field(self.kind, "detail_unknown")
        assert not documents.is_filled_field(self.kind, "place_date")


@override_settings(**CREDITOR)
class RenderMandateTest(TestCase):
    def test_contains_reference_creditor_and_bank_data(self):
        mandate = SepaMandateFactory(account_holder="Holder e.V.", bic="COBADEFFXXX")

        content = documents.render_mandate(mandate)

        text = PdfReader(BytesIO(content)).pages[0].extract_text()
        assert mandate.reference in text
        assert "DE98ZZZ09999999999" in text
        assert "Example Street 1, 12345 Example City" in text
        assert "Holder e.V." in text
        assert "DE89 3704 0044 0532 0130 00" in text
        assert "COBADEFFXXX" in text
        assert mandate.agreement.kind.name in text
        assert mandate.agreement.organization.name in text


class ContractDownloadViewTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template()
        self.agreement = AgreementFactory(kind=self.kind)
        self.admin = make_admin(self.agreement.organization)
        self.url = reverse(
            "agreements:contract-document", kwargs={"agreement": self.agreement.uuid}
        )

    def test_admin_downloads(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith("attachment;")
        assert response["Cache-Control"] == "no-store"
        page = self.client.get(self.agreement.get_absolute_url()).content.decode()
        assert self.url in page

    def test_downloading_admin_is_representative_without_contact_person(self):
        self.client.force_login(self.admin)

        values = _values(self.client.get(self.url).content)

        assert values["representative_name"] == self.admin.get_full_name()

    def test_manager_gets_empty_representative(self):
        self.client.force_login(make_manager(self.kind.organization_group))

        values = _values(self.client.get(self.url).content)

        assert values["representative_name"] in (None, "")

    def test_contact_person_wins(self):
        contact = UserFactory()
        self.agreement.contact_person = contact
        self.agreement.save()
        self.client.force_login(self.admin)

        values = _values(self.client.get(self.url).content)

        assert values["representative_name"] == contact.get_full_name()

    def test_denied_for_others(self):
        self.client.force_login(make_booker(self.agreement.organization))
        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

        self.client.force_login(make_manager(OrganizationGroupFactory()))
        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

    def test_not_found_without_template_or_when_closed(self):
        self.client.force_login(self.admin)
        self.agreement.status = Agreement.Status.ENDED
        self.agreement.save()
        assert self.client.get(self.url).status_code == HTTPStatus.NOT_FOUND
        page = self.client.get(self.agreement.get_absolute_url()).content.decode()
        assert self.url not in page

        other = AgreementFactory(organization=self.agreement.organization)
        url = reverse("agreements:contract-document", kwargs={"agreement": other.uuid})
        assert self.client.get(url).status_code == HTTPStatus.NOT_FOUND


@override_settings(**CREDITOR)
class MandateDownloadViewTest(TestCase):
    def setUp(self):
        self.mandate = SepaMandateFactory(signed_document=None, signed_on=None)
        self.organization = self.mandate.agreement.organization
        self.url = reverse(
            "agreements:mandate-document", kwargs={"mandate": self.mandate.uuid}
        )

    def test_admin_downloads(self):
        self.client.force_login(make_admin(self.organization))

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert response["Cache-Control"] == "no-store"
        assert self.mandate.reference in response["Content-Disposition"]

    def test_booker_denied(self):
        self.client.force_login(make_booker(self.organization))

        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

    def test_revoked_not_found(self):
        self.mandate.revoked_on = date(2027, 1, 1)
        self.mandate.save()
        self.client.force_login(make_admin(self.organization))

        assert self.client.get(self.url).status_code == HTTPStatus.NOT_FOUND


class ApplicationMessageTest(TestCase):
    def test_points_to_prefilled_contract(self):
        kind = _kind_with_template()
        agreement = AgreementFactory()
        organization = agreement.organization
        self.client.force_login(make_admin(organization))
        url = reverse(
            "agreements:apply",
            kwargs={"organization": organization.slug, "kind": kind.slug},
        )

        response = self.client.post(
            url,
            {
                "start_date": "2027-03-01",
                "amount": "80",
                "contact_person_function": "Chair",
                "detail_area": "",
                "area": "10",
                "since": "2026-05-01",
            },
            follow=True,
        )

        assert "Download the prefilled contract below" in response.content.decode()
