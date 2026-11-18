"""Signing online: contracts, SEPA mandates and the countersignature."""

from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from re_sharing.agreements.forms import ApplicationForm
from re_sharing.agreements.forms import DecisionForm
from re_sharing.agreements.forms import ManagerAgreementEditForm
from re_sharing.agreements.forms import ManagerAgreementForm
from re_sharing.agreements.forms import MandateForm
from re_sharing.agreements.forms import SignedDocumentForm
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import SepaMandate
from re_sharing.agreements.services import AgreementError
from re_sharing.agreements.services import approve_agreement
from re_sharing.agreements.services import create_agreement
from re_sharing.agreements.services import create_mandate
from re_sharing.agreements.services import reject_agreement
from re_sharing.agreements.services import upload_signed_document
from re_sharing.agreements.services import upload_signed_mandate
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import fillable_pdf
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_booker
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.utils.tests.helpers import readable_pdf_file
from re_sharing.utils.tests.helpers import signature_data

CREDITOR = {
    "SEPA_CREDITOR_NAME": "Example Creditor e.V.",
    "SEPA_CREDITOR_ADDRESS": "Example Street 1, 12345 Example City",
    "SEPA_CREDITOR_ID": "DE98ZZZ09999999999",
}
APPLICATION = {
    "start_date": "2027-10-10",
    "amount": "80",
    "contact_person_function": "Board",
}
BANK_DATA = {"account_holder": "Example e.V.", "iban": VALID_IBAN}
TEMPLATE_FIELDS = ("organization_name", "representative_name", "amount")


def _kind_with_template(**kwargs):
    return MembershipKindFactory(
        name="Membership", contract_template=fillable_pdf(TEMPLATE_FIELDS), **kwargs
    )


def _stored(file_field) -> PdfReader:
    with file_field.open("rb") as stored:
        return PdfReader(BytesIO(stored.read()))


def _last_page(file_field) -> str:
    return _stored(file_field).pages[-1].extract_text()


def _valid(form):
    assert form.is_valid(), form.errors
    return form


def _signed_application(kind, organization):
    data = {**APPLICATION, **signature_data()}
    return _valid(ApplicationForm(data=data, kind=kind, signing_for=organization.name))


def _signature_form(organization, name="Ada Example"):
    return _valid(
        SignedDocumentForm(data=signature_data(name), signing_for=organization.name)
    )


def _upload_form(file=None):
    return _valid(
        SignedDocumentForm(
            data={"signed_on": "2027-02-01"},
            files={"signed_document": file or pdf_file()},
        )
    )


# =============================================================================
# Forms
# =============================================================================


class SigningFormsTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template()

    def test_application_form_offers_signing_for_a_kind_with_template(self):
        form = ApplicationForm(kind=self.kind, signing_for="Example Organization")

        assert list(form.fields)[-2:] == ["signature_name", "signature_image"]
        assert "Example Organization" in form.fields["signature_image"].help_text

    def test_application_form_without_template_offers_only_the_upload(self):
        form = ApplicationForm(kind=MembershipKindFactory(), signing_for="Example")

        assert "signature_image" not in form.fields
        assert "signed_document" in form.fields

    def test_manager_forms_never_offer_signing(self):
        agreement = AgreementFactory(kind=self.kind)

        create = ManagerAgreementForm(kind=self.kind, signing_for="Example")
        edit = ManagerAgreementEditForm(agreement=agreement, signing_for="Example")

        assert "signature_image" not in create.fields
        assert "signature_image" not in edit.fields

    def test_signature_replaces_the_required_upload(self):
        form = SignedDocumentForm(data=signature_data(), signing_for="Example")

        assert form.is_valid(), form.errors
        assert form.signature is not None

    def test_neither_upload_nor_signature(self):
        form = SignedDocumentForm(data={}, signing_for="Example")

        assert not form.is_valid()
        assert "sign online" in form.errors["signed_document"][0]

    def test_neither_upload_nor_signature_without_signing(self):
        form = SignedDocumentForm(data={})

        assert not form.is_valid()
        assert form.errors["signed_document"] == ["Upload the signed PDF."]

    def test_upload_and_signature_refused(self):
        form = SignedDocumentForm(
            data={"signed_on": "2027-02-01", **signature_data()},
            files={"signed_document": pdf_file()},
            signing_for="Example",
        )

        assert not form.is_valid()
        assert "not both" in form.non_field_errors()[0]

    def test_typed_date_is_no_error_when_signing_online(self):
        form = SignedDocumentForm(
            data={"signed_on": "2027-02-01", **signature_data()}, signing_for="Example"
        )

        assert form.is_valid(), form.errors

    def test_decision_form_takes_a_signature_only_when_countersigning(self):
        assert "signature_image" not in DecisionForm().fields
        assert "signature_image" in DecisionForm(signing_for="Example").fields


# =============================================================================
# Contracts
# =============================================================================


class SignContractTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template()
        self.organization = OrganizationFactory(
            name="Example Organization", status=Organization.Status.CONFIRMED
        )
        self.member = make_booker(self.organization)

    def test_signed_with_the_application(self):
        form = _signed_application(self.kind, self.organization)

        agreement = create_agreement(self.member, self.organization, self.kind, form)

        agreement.refresh_from_db()
        assert agreement.has_complete_signed_document
        assert agreement.signed_on == timezone.localdate()
        contract = _stored(agreement.signed_document)
        expected_pages = 2
        assert len(contract.pages) == expected_pages
        fields = contract.get_fields()
        assert fields["amount"]["/V"] == "80,00"
        assert fields["organization_name"]["/V"] == "Example Organization"
        assert fields["representative_name"]["/V"] == self.member.get_full_name()
        page = contract.pages[-1].extract_text()
        for expected in (
            "Membership",
            "Example Organization",
            "Ada Example",
            "Board",
            self.member.email,
        ):
            assert expected in page

    def test_applied_without_upload_or_signature(self):
        form = _valid(
            ApplicationForm(
                data=APPLICATION, kind=self.kind, signing_for=self.organization.name
            )
        )

        agreement = create_agreement(self.member, self.organization, self.kind, form)

        assert not agreement.signed_document
        assert agreement.signed_on is None

    def test_signed_later(self):
        agreement = AgreementFactory(kind=self.kind, organization=self.organization)

        upload_signed_document(
            self.member, agreement, _signature_form(self.organization)
        )

        agreement.refresh_from_db()
        assert agreement.signed_on == timezone.localdate()
        assert "Ada Example" in _last_page(agreement.signed_document)

    def test_upload_replaces_a_contract_signed_online(self):
        agreement = AgreementFactory(kind=self.kind, organization=self.organization)
        upload_signed_document(
            self.member, agreement, _signature_form(self.organization)
        )

        upload_signed_document(
            self.member, agreement, _upload_form(readable_pdf_file(pages=3))
        )

        agreement.refresh_from_db()
        assert agreement.signed_on == date(2027, 2, 1)
        expected_pages = 3
        assert len(_stored(agreement.signed_document).pages) == expected_pages

    def test_manager_cannot_sign_for_the_organization(self):
        agreement = AgreementFactory(kind=self.kind, organization=self.organization)

        with pytest.raises(PermissionDenied):
            upload_signed_document(
                make_manager(), agreement, _signature_form(self.organization)
            )

        assert not agreement.signed_document

    def test_active_agreement_cannot_be_signed_online(self):
        agreement = AgreementFactory(
            kind=self.kind,
            organization=self.organization,
            status=Agreement.Status.ACTIVE,
        )

        with pytest.raises(PermissionDenied):
            upload_signed_document(
                self.member, agreement, _signature_form(self.organization)
            )

    def test_kind_without_template_cannot_be_signed_online(self):
        agreement = AgreementFactory(organization=self.organization)

        with pytest.raises(PermissionDenied):
            upload_signed_document(
                self.member, agreement, _signature_form(self.organization)
            )


class SignContractViewTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.member = make_admin(self.organization)
        self.client.force_login(self.member)

    def _agreement(self, **kwargs):
        return AgreementFactory(
            kind=self.kind, organization=self.organization, **kwargs
        )

    def _upload_url(self, agreement):
        return reverse(
            "agreements:upload-signed-document", kwargs={"agreement": agreement.uuid}
        )

    def test_application_page_shows_the_pad(self):
        url = reverse(
            "agreements:apply",
            kwargs={"organization": self.organization.slug, "kind": self.kind.slug},
        )

        content = self.client.get(url).content.decode()

        assert 'name="signature_image"' in content
        assert "signature_pad" in content

    def test_apply_and_sign(self):
        url = reverse(
            "agreements:apply",
            kwargs={"organization": self.organization.slug, "kind": self.kind.slug},
        )

        response = self.client.post(
            url, {**APPLICATION, **signature_data()}, follow=True
        )

        agreement = Agreement.objects.get()
        assert agreement.signed_on == timezone.localdate()
        assert "Ada Example" in _last_page(agreement.signed_document)
        assert "Your application was submitted." in response.content.decode()

    def test_agreement_page_offers_signing_while_submitted(self):
        content = self.client.get(self._agreement().get_absolute_url()).content.decode()

        assert 'name="signature_image"' in content
        assert "Sign or upload the contract" in content

    def test_open_form_while_the_contract_is_missing(self):
        content = self.client.get(self._agreement().get_absolute_url()).content.decode()

        assert '<div id="contract-form"' in content
        assert 'class="collapse"' not in content
        assert "Replace the contract" not in content

    def test_form_is_collapsed_once_a_contract_is_stored(self):
        agreement = self._agreement(with_signed_document=True)

        content = self.client.get(agreement.get_absolute_url()).content.decode()

        assert "Replace the contract" in content
        assert 'data-bs-target="#contract-form"' in content
        assert 'class="collapse"' in content
        assert "Signing again or uploading replaces the stored contract." in content
        assert "Sign or upload the contract" not in content
        assert 'name="signature_image"' in content

    def test_manager_replaces_by_upload_only(self):
        agreement = self._agreement(with_signed_document=True)
        self.client.force_login(make_manager())

        content = self.client.get(agreement.get_absolute_url()).content.decode()

        assert "An upload replaces the stored contract." in content
        assert 'name="signature_image"' not in content

    def test_active_agreement_offers_only_the_upload(self):
        agreement = self._agreement(status=Agreement.Status.ACTIVE)

        content = self.client.get(agreement.get_absolute_url()).content.decode()

        assert 'name="signature_image"' not in content
        assert 'name="signed_document"' in content

    def test_kind_without_template_offers_only_the_upload(self):
        agreement = AgreementFactory(organization=self.organization)

        content = self.client.get(agreement.get_absolute_url()).content.decode()

        assert 'name="signature_image"' not in content

    def test_manager_is_offered_only_the_upload(self):
        self.client.force_login(make_manager())

        content = self.client.get(self._agreement().get_absolute_url()).content.decode()

        assert 'name="signed_document"' in content
        assert 'name="signature_image"' not in content

    def test_sign_later(self):
        agreement = self._agreement()

        response = self.client.post(
            self._upload_url(agreement), signature_data(), follow=True
        )

        agreement.refresh_from_db()
        assert agreement.signed_document
        assert "The contract was signed." in response.content.decode()

    def test_unreadable_drawing_signs_nothing(self):
        agreement = self._agreement()

        response = self.client.post(
            self._upload_url(agreement),
            {"signature_name": "Ada Example", "signature_image": "data:,broken"},
            follow=True,
        )

        agreement.refresh_from_db()
        assert not agreement.signed_document
        assert "could not be read" in response.content.decode()

    def test_upload_still_works(self):
        agreement = self._agreement()

        response = self.client.post(
            self._upload_url(agreement),
            {"signed_on": "2027-02-01", "signed_document": pdf_file()},
            follow=True,
        )

        agreement.refresh_from_db()
        assert agreement.signed_on == date(2027, 2, 1)
        assert "The signed contract was uploaded." in response.content.decode()


# =============================================================================
# Mandates
# =============================================================================


def _mandate_form(organization, **data):
    return _valid(
        MandateForm(data={**BANK_DATA, **data}, signing_for=organization.name)
    )


@override_settings(
    SEPA_MANDATE_PREFIX="RS", SEPA_MANDATE_REFERENCE_PREFIX="RS-VM", **CREDITOR
)
class SignMandateTest(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory(
            name="Example Organization", status=Organization.Status.CONFIRMED
        )
        self.agreement = AgreementFactory(
            organization=self.organization, contact_person_function="Treasurer"
        )
        self.member = make_admin(self.organization)

    def test_signed_when_saving(self):
        form = _mandate_form(self.organization, **signature_data())

        mandate = create_mandate(self.member, self.agreement, form)

        mandate.refresh_from_db()
        assert mandate.is_active
        assert mandate.signed_on == timezone.localdate()
        document = _stored(mandate.signed_document)
        expected_pages = 2
        assert len(document.pages) == expected_pages
        first = document.pages[0].extract_text()
        assert mandate.reference in first
        assert "DE98ZZZ09999999999" in first
        assert "DE89 3704 0044 0532 0130 00" in first
        last = document.pages[1].extract_text()
        for expected in (
            mandate.reference,
            "Example Organization",
            "Ada Example",
            "Treasurer",
            self.member.email,
        ):
            assert expected in last

    def test_saved_without_signature(self):
        mandate = create_mandate(
            self.member, self.agreement, _mandate_form(self.organization)
        )

        assert not mandate.signed_document
        assert not mandate.is_active

    def test_signed_document_shows_the_reference_of_a_retry(self):
        SepaMandateFactory(reference="RS-VM-001")
        form = _mandate_form(self.organization, **signature_data())

        with patch(
            "re_sharing.agreements.services.generate_mandate_reference",
            side_effect=["RS-VM-001", "RS-VM-002"],
        ):
            mandate = create_mandate(self.member, self.agreement, form)

        mandate.refresh_from_db()
        assert mandate.reference == "RS-VM-002"
        document = _stored(mandate.signed_document)
        assert "RS-VM-002" in document.pages[0].extract_text()
        assert "RS-VM-002" in document.pages[1].extract_text()

    def test_signed_later(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, signed_on=None
        )

        upload_signed_mandate(self.member, mandate, _signature_form(self.organization))

        mandate.refresh_from_db()
        assert mandate.is_active
        assert mandate.signed_on == timezone.localdate()
        assert "Ada Example" in _last_page(mandate.signed_document)

    def test_upload_still_works(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, signed_on=None
        )

        upload_signed_mandate(self.member, mandate, _upload_form())

        mandate.refresh_from_db()
        assert mandate.signed_on == date(2027, 2, 1)

    def test_manager_cannot_sign_for_the_organization(self):
        manager = make_manager()
        form = _mandate_form(self.organization, **signature_data())

        with pytest.raises(PermissionDenied):
            create_mandate(manager, self.agreement, form)

        assert not SepaMandate.objects.exists()


@override_settings(
    SEPA_MANDATE_PREFIX="RS", SEPA_MANDATE_REFERENCE_PREFIX="RS-VM", **CREDITOR
)
class SignMandateViewTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory()
        self.member = make_admin(self.agreement.organization)
        self.client.force_login(self.member)
        self.create_url = reverse(
            "agreements:create-mandate", kwargs={"agreement": self.agreement.uuid}
        )

    def test_mandate_form_shows_the_pad(self):
        content = self.client.get(self.create_url).content.decode()

        assert 'name="signature_image"' in content

    def test_manager_is_offered_only_the_upload(self):
        self.client.force_login(make_manager())

        content = self.client.get(self.create_url).content.decode()

        assert 'name="signed_document"' in content
        assert 'name="signature_image"' not in content

    def test_save_and_sign(self):
        self.client.post(self.create_url, {**BANK_DATA, **signature_data()})

        mandate = SepaMandate.objects.get()
        assert mandate.is_active
        assert "Ada Example" in _last_page(mandate.signed_document)

    def test_invalid_iban_creates_nothing(self):
        response = self.client.post(
            self.create_url,
            {"account_holder": "Example", "iban": "DE00", **signature_data()},
        )

        assert not SepaMandate.objects.exists()
        assert "iban" in response.context["form"].errors

    def test_sign_later_from_the_mandate_page(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, signed_on=None
        )
        assert 'name="signature_image"' in (
            self.client.get(mandate.get_absolute_url()).content.decode()
        )
        url = reverse(
            "agreements:upload-signed-mandate", kwargs={"mandate": mandate.uuid}
        )

        response = self.client.post(url, signature_data(), follow=True)

        mandate.refresh_from_db()
        assert mandate.is_active
        assert "The mandate was signed." in response.content.decode()

    def test_upload_from_the_mandate_page(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, signed_on=None
        )
        url = reverse(
            "agreements:upload-signed-mandate", kwargs={"mandate": mandate.uuid}
        )

        response = self.client.post(
            url, {"signed_on": "2027-02-01", "signed_document": pdf_file()}, follow=True
        )

        assert "The signed mandate was uploaded." in response.content.decode()

    def test_missing_name_signs_nothing(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, signed_on=None
        )
        url = reverse(
            "agreements:upload-signed-mandate", kwargs={"mandate": mandate.uuid}
        )
        data = signature_data()
        del data["signature_name"]

        response = self.client.post(url, data, follow=True)

        mandate.refresh_from_db()
        assert not mandate.signed_document
        assert "Type your name to sign." in response.content.decode()


# =============================================================================
# Countersignature
# =============================================================================


def _countersignature(name="Maxi Director"):
    return _valid(
        DecisionForm(
            data={"decided_at": "2027-03-10", **signature_data(name)},
            signing_for="Example Creditor e.V.",
        )
    ).signature


@override_settings(PRE_NOTIFICATION_DAYS=14, **CREDITOR)
class CountersignOnApprovalTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template(requires_countersignature=True)
        self.agreement = AgreementFactory(kind=self.kind)
        self.agreement.signed_document = readable_pdf_file(pages=2)
        self.agreement.signed_on = date(2027, 3, 1)
        self.agreement.save()
        SepaMandateFactory(agreement=self.agreement)
        self.signatory = make_manager(self.kind.organization_group)
        self.signatory.manager.signatory_title = "Managing director"
        self.signatory.manager.save()
        self.decided_at = date(2027, 3, 10)

    def _approve(self, user=None, signature="default"):
        if signature == "default":
            signature = _countersignature()
        return approve_agreement(
            user or self.signatory, self.agreement, self.decided_at, signature
        )

    def _assert_untouched(self):
        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.SUBMITTED
        expected_pages = 2
        assert len(_stored(self.agreement.signed_document).pages) == expected_pages

    def test_approve_and_countersign_an_uploaded_contract(self):
        self._approve()

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ACTIVE
        assert self.agreement.decided_at == self.decided_at
        assert self.agreement.decided_by == self.signatory
        assert self.agreement.signed_on == date(2027, 3, 1)
        assert self.kind.organization_group in (
            self.agreement.organization.organization_groups.all()
        )
        contract = _stored(self.agreement.signed_document)
        expected_pages = 3
        assert len(contract.pages) == expected_pages
        assert "Source page 2" in contract.pages[1].extract_text()
        page = contract.pages[2].extract_text()
        for expected in (
            "Maxi Director",
            "Managing director",
            "Example Creditor e.V.",
            self.signatory.email,
        ):
            assert expected in page

    def test_contract_signed_online_gets_a_second_signature_page(self):
        organization = self.agreement.organization
        upload_signed_document(
            make_admin(organization), self.agreement, _signature_form(organization)
        )

        self._approve()

        contract = _stored(self.agreement.signed_document)
        expected_pages = 3
        assert len(contract.pages) == expected_pages
        assert "Ada Example" in contract.pages[1].extract_text()
        assert "Maxi Director" in contract.pages[2].extract_text()

    def test_manager_without_title_refused(self):
        manager = make_manager(self.kind.organization_group)

        with pytest.raises(AgreementError) as refused:
            self._approve(user=manager)

        assert "authorized signatory" in refused.value.message
        self._assert_untouched()

    def test_approval_without_signature_refused(self):
        with pytest.raises(AgreementError) as refused:
            self._approve(signature=None)

        assert "Sign the contract" in refused.value.message
        self._assert_untouched()

    def test_unreadable_upload_refused(self):
        self.agreement.signed_document = pdf_file()
        self.agreement.save()

        with pytest.raises(AgreementError) as refused:
            self._approve()

        assert "cannot be read" in refused.value.message
        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.SUBMITTED

    def test_failing_approval_leaves_the_document_unchanged(self):
        with (
            patch(
                "re_sharing.agreements.services_collections."
                "create_first_period_collection",
                side_effect=RuntimeError,
            ),
            pytest.raises(RuntimeError),
        ):
            self._approve()

        self._assert_untouched()

    def test_missing_mandate_is_named_before_the_signature(self):
        SepaMandate.objects.all().delete()

        with pytest.raises(AgreementError) as refused:
            self._approve(signature=None)

        assert "mandate" in refused.value.message

    def test_kind_without_countersignature_is_approved_as_before(self):
        self.kind.requires_countersignature = False
        self.kind.save()
        manager = make_manager(self.kind.organization_group)

        self._approve(user=manager, signature=None)

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ACTIVE
        expected_pages = 2
        assert len(_stored(self.agreement.signed_document).pages) == expected_pages

    def test_rejection_needs_neither_title_nor_signature(self):
        manager = make_manager(self.kind.organization_group)

        reject_agreement(manager, self.agreement, self.decided_at)

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.REJECTED

    @override_settings(SEPA_CREDITOR_NAME="")
    def test_operator_without_configured_name(self):
        self._approve()

        assert "the operator" in _last_page(self.agreement.signed_document)


@override_settings(PRE_NOTIFICATION_DAYS=14, **CREDITOR)
class CountersignViewTest(TestCase):
    def setUp(self):
        self.kind = _kind_with_template(requires_countersignature=True)
        self.agreement = AgreementFactory(kind=self.kind)
        self.agreement.signed_document = readable_pdf_file()
        self.agreement.signed_on = date(2027, 3, 1)
        self.agreement.save()
        SepaMandateFactory(agreement=self.agreement)
        self.signatory = make_manager(self.kind.organization_group)
        self.signatory.manager.signatory_title = "Managing director"
        self.signatory.manager.save()
        self.client.force_login(self.signatory)

    def _post(self, name, data):
        url = reverse(name, kwargs={"agreement": self.agreement.uuid})
        response = self.client.post(url, data, follow=True)
        self.agreement.refresh_from_db()
        return response.content.decode()

    def test_approval_form_shows_the_pad(self):
        content = self.client.get(self.agreement.get_absolute_url()).content.decode()

        assert 'name="signature_image"' in content
        assert "Example Creditor e.V." in content

    def test_kind_without_countersignature_shows_no_pad(self):
        self.kind.requires_countersignature = False
        self.kind.save()

        content = self.client.get(self.agreement.get_absolute_url()).content.decode()

        assert 'name="signature_image"' not in content

    def test_manager_without_title_sees_no_approval(self):
        self.client.force_login(make_manager(self.kind.organization_group))

        content = self.client.get(self.agreement.get_absolute_url()).content.decode()

        assert "Only managers with a signatory title can approve it" in content
        assert 'name="signature_image"' not in content
        assert "btn btn-success" not in content
        assert "/reject/" in content

    def test_approve_and_countersign(self):
        content = self._post(
            "agreements:manager-approve-agreement",
            {"decided_at": "2027-03-10", **signature_data("Maxi Director")},
        )

        assert self.agreement.status == Agreement.Status.ACTIVE
        assert "The decision was recorded." in content
        assert "Maxi Director" in _last_page(self.agreement.signed_document)

    def test_approve_without_signature_refused(self):
        content = self._post(
            "agreements:manager-approve-agreement", {"decided_at": "2027-03-10"}
        )

        assert self.agreement.status == Agreement.Status.SUBMITTED
        assert "Sign the contract to approve this agreement." in content

    def test_approve_with_drawing_but_no_name_refused(self):
        data = signature_data()
        del data["signature_name"]

        content = self._post(
            "agreements:manager-approve-agreement", {"decided_at": "2027-03-10", **data}
        )

        assert self.agreement.status == Agreement.Status.SUBMITTED
        assert "Type your name to sign." in content

    def test_approve_without_date(self):
        content = self._post("agreements:manager-approve-agreement", signature_data())

        assert self.agreement.status == Agreement.Status.SUBMITTED
        assert "Enter the date of the board decision." in content

    def test_manager_without_title_refused(self):
        self.client.force_login(make_manager(self.kind.organization_group))

        content = self._post(
            "agreements:manager-approve-agreement",
            {"decided_at": "2027-03-10", **signature_data()},
        )

        assert self.agreement.status == Agreement.Status.SUBMITTED
        assert "authorized signatory" in content

    def test_reject_without_signature(self):
        self.client.force_login(make_manager(self.kind.organization_group))

        self._post("agreements:manager-reject-agreement", {"decided_at": "2027-03-10"})

        assert self.agreement.status == Agreement.Status.REJECTED

    def test_reject_ignores_a_half_filled_signature(self):
        self._post(
            "agreements:manager-reject-agreement",
            {"decided_at": "2027-03-10", "signature_name": "Maxi Director"},
        )

        assert self.agreement.status == Agreement.Status.REJECTED


# =============================================================================
# Replacing signed documents once the agreement is decided
# =============================================================================


class ReplaceSignedDocumentsTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(
            status=Agreement.Status.ACTIVE, with_signed_document=True
        )
        self.member = make_admin(self.agreement.organization)
        self.manager = make_manager()

    def _contract_name(self):
        self.agreement.refresh_from_db()
        return self.agreement.signed_document.name

    def test_member_cannot_replace_the_contract_of_an_active_agreement(self):
        before = self._contract_name()

        with pytest.raises(AgreementError) as refused:
            upload_signed_document(self.member, self.agreement, _upload_form())

        assert "only be replaced by a manager" in refused.value.message
        assert self._contract_name() == before

    def test_manager_replaces_the_contract_of_an_active_agreement(self):
        before = self._contract_name()

        upload_signed_document(self.manager, self.agreement, _upload_form())

        assert self._contract_name() != before

    def test_member_adds_a_missing_contract_to_an_active_agreement(self):
        agreement = AgreementFactory(
            status=Agreement.Status.ACTIVE, organization=self.agreement.organization
        )

        upload_signed_document(self.member, agreement, _upload_form())

        agreement.refresh_from_db()
        assert agreement.signed_document

    def test_member_replaces_the_contract_while_submitted(self):
        agreement = AgreementFactory(
            organization=self.agreement.organization, with_signed_document=True
        )
        before = agreement.signed_document.name

        upload_signed_document(self.member, agreement, _upload_form())

        agreement.refresh_from_db()
        assert agreement.signed_document.name != before

    def test_member_cannot_replace_the_mandate_of_an_active_agreement(self):
        mandate = SepaMandateFactory(agreement=self.agreement)
        before = mandate.signed_document.name

        with pytest.raises(AgreementError) as refused:
            upload_signed_mandate(self.member, mandate, _upload_form())

        assert "only be replaced by a manager" in refused.value.message
        mandate.refresh_from_db()
        assert mandate.signed_document.name == before

    def test_manager_replaces_the_mandate_of_an_active_agreement(self):
        mandate = SepaMandateFactory(agreement=self.agreement)
        before = mandate.signed_document.name

        upload_signed_mandate(self.manager, mandate, _upload_form())

        mandate.refresh_from_db()
        assert mandate.signed_document.name != before

    def test_member_signs_a_new_mandate_of_an_active_agreement(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, signed_on=None
        )

        upload_signed_mandate(self.member, mandate, _upload_form())

        mandate.refresh_from_db()
        assert mandate.is_active

    def test_member_replaces_the_mandate_while_submitted(self):
        mandate = SepaMandateFactory(
            agreement=AgreementFactory(organization=self.agreement.organization)
        )
        before = mandate.signed_document.name

        upload_signed_mandate(self.member, mandate, _upload_form())

        mandate.refresh_from_db()
        assert mandate.signed_document.name != before

    def test_member_sees_no_replace_button_on_an_active_agreement(self):
        self.client.force_login(self.member)

        content = self.client.get(self.agreement.get_absolute_url()).content.decode()

        assert "Replace the contract" not in content
        assert 'name="signed_document"' not in content

    def test_manager_sees_the_replace_button_on_an_active_agreement(self):
        self.client.force_login(self.manager)

        content = self.client.get(self.agreement.get_absolute_url()).content.decode()

        assert "Replace the contract" in content

    def test_refused_replacement_shows_a_message(self):
        self.client.force_login(self.member)
        url = reverse(
            "agreements:upload-signed-document",
            kwargs={"agreement": self.agreement.uuid},
        )

        response = self.client.post(
            url, {"signed_on": "2027-02-01", "signed_document": pdf_file()}, follow=True
        )

        assert "only be replaced by a manager" in response.content.decode()
