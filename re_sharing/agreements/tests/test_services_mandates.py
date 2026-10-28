from datetime import date

import pytest
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.test import override_settings

from re_sharing.agreements.forms import MandateForm
from re_sharing.agreements.forms import SignedDocumentForm
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.services import AgreementError
from re_sharing.agreements.services import create_mandate
from re_sharing.agreements.services import generate_collection_reference
from re_sharing.agreements.services import generate_mandate_reference
from re_sharing.agreements.services import revoke_mandate
from re_sharing.agreements.services import upload_signed_mandate
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_booker
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.tests.factories import OrganizationGroupFactory


def _mandate_form(with_pdf=False):  # noqa: FBT002
    data = {"account_holder": "Example e.V.", "iban": VALID_IBAN}
    files = {}
    if with_pdf:
        data["signed_on"] = "2027-02-01"
        files["signed_document"] = pdf_file()
    form = MandateForm(data=data, files=files)
    assert form.is_valid(), form.errors
    return form


@override_settings(SEPA_MANDATE_PREFIX="RS")
class ReferenceTest(TestCase):
    def test_first_mandate_reference(self):
        agreement = AgreementFactory()

        assert generate_mandate_reference(agreement) == f"RS-{agreement.id:06d}-1"

    def test_reference_after_revocation(self):
        agreement = AgreementFactory()
        SepaMandateFactory(
            agreement=agreement,
            reference=f"RS-{agreement.id:06d}-1",
            revoked_on=date(2027, 1, 1),
        )

        assert generate_mandate_reference(agreement) == f"RS-{agreement.id:06d}-2"

    def test_skips_hand_entered_reference(self):
        agreement = AgreementFactory()
        SepaMandateFactory(reference=f"RS-{agreement.id:06d}-1")

        assert generate_mandate_reference(agreement) == f"RS-{agreement.id:06d}-2"

    def test_collection_reference(self):
        collection = CollectionFactory()

        assert generate_collection_reference(collection) == (
            f"RS-C-{collection.id:06d}"
        )


class CreateMandateTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory()
        self.admin = make_admin(self.agreement.organization)

    def test_admin_saves_mandate_without_pdf(self):
        mandate = create_mandate(self.admin, self.agreement, _mandate_form())

        assert mandate.reference.endswith(f"{self.agreement.id:06d}-1")
        assert mandate.iban == VALID_IBAN
        assert not mandate.is_active

    def test_admin_saves_mandate_with_pdf(self):
        mandate = create_mandate(
            self.admin, self.agreement, _mandate_form(with_pdf=True)
        )

        assert mandate.is_active
        assert mandate.signed_on == date(2027, 2, 1)

    def test_second_open_mandate_refused(self):
        create_mandate(self.admin, self.agreement, _mandate_form())

        with pytest.raises(AgreementError, match="revoke"):
            create_mandate(self.admin, self.agreement, _mandate_form())

    def test_booker_denied(self):
        booker = make_booker(self.agreement.organization)

        with pytest.raises(PermissionDenied):
            create_mandate(booker, self.agreement, _mandate_form())

    def test_manager_in_scope_allowed(self):
        manager = make_manager(self.agreement.kind.organization_group)

        assert create_mandate(manager, self.agreement, _mandate_form())

    def test_ended_agreement_refused(self):
        self.agreement.status = Agreement.Status.ENDED
        self.agreement.save()

        with pytest.raises(AgreementError):
            create_mandate(self.admin, self.agreement, _mandate_form())


class UploadAndRevokeMandateTest(TestCase):
    def setUp(self):
        self.mandate = SepaMandateFactory(signed_document=None, signed_on=None)
        self.admin = make_admin(self.mandate.agreement.organization)

    def _upload_form(self):
        form = SignedDocumentForm(
            data={"signed_on": "2027-02-03"}, files={"signed_document": pdf_file()}
        )
        assert form.is_valid()
        return form

    def test_upload_makes_mandate_active(self):
        upload_signed_mandate(self.admin, self.mandate, self._upload_form())

        self.mandate.refresh_from_db()
        assert self.mandate.is_active
        assert self.mandate.signed_on == date(2027, 2, 3)

    def test_upload_denied_for_foreign_user(self):
        other = make_admin(AgreementFactory().organization)

        with pytest.raises(PermissionDenied):
            upload_signed_mandate(other, self.mandate, self._upload_form())

    def test_upload_on_revoked_refused(self):
        self.mandate.revoked_on = date(2027, 1, 1)
        self.mandate.save()

        with pytest.raises(AgreementError):
            upload_signed_mandate(self.admin, self.mandate, self._upload_form())

    def test_manager_revokes(self):
        manager = make_manager()

        revoke_mandate(manager, self.mandate, date(2027, 4, 1))

        self.mandate.refresh_from_db()
        assert self.mandate.revoked_on == date(2027, 4, 1)

    def test_revoke_twice_refused(self):
        manager = make_manager()
        revoke_mandate(manager, self.mandate, date(2027, 4, 1))

        with pytest.raises(AgreementError):
            revoke_mandate(manager, self.mandate, date(2027, 4, 2))

    def test_admin_cannot_revoke(self):
        with pytest.raises(PermissionDenied):
            revoke_mandate(self.admin, self.mandate, date(2027, 4, 1))

    def test_manager_out_of_scope_cannot_revoke(self):
        manager = make_manager(OrganizationGroupFactory())

        with pytest.raises(PermissionDenied):
            revoke_mandate(manager, self.mandate, date(2027, 4, 1))
