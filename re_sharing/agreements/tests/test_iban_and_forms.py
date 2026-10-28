from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.test import TestCase

from re_sharing.agreements.forms import MandateForm
from re_sharing.agreements.forms import SignedDocumentForm
from re_sharing.agreements.iban import normalize_iban
from re_sharing.agreements.iban import validate_iban
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import pdf_file


class IbanTest(SimpleTestCase):
    def test_normalize_removes_spaces_and_uppercases(self):
        assert normalize_iban(" de89 3704 0044 0532 0130 00 ") == VALID_IBAN

    def test_valid_iban(self):
        validate_iban(VALID_IBAN)
        validate_iban("DE02 1203 0000 0000 2020 51")

    def test_wrong_checksum(self):
        with pytest.raises(ValidationError):
            validate_iban("DE00370400440532013000")

    def test_wrong_format(self):
        with pytest.raises(ValidationError):
            validate_iban("12345")


class MandateFormTest(TestCase):
    def _data(self, **overrides):
        data = {
            "account_holder": "Example e.V.",
            "iban": "DE89 3704 0044 0532 0130 00",
            "bic": "cobadeffxxx",
        }
        data.update(overrides)
        return data

    def test_valid_without_signed_pdf(self):
        form = MandateForm(data=self._data())

        assert form.is_valid(), form.errors
        assert form.cleaned_data["iban"] == VALID_IBAN
        assert form.cleaned_data["bic"] == "COBADEFFXXX"

    def test_valid_with_signed_pdf_and_date(self):
        form = MandateForm(
            data=self._data(signed_on="2027-02-01"),
            files={"signed_document": pdf_file()},
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["signed_on"] == date(2027, 2, 1)

    def test_invalid_iban(self):
        form = MandateForm(data=self._data(iban="DE00370400440532013000"))

        assert not form.is_valid()
        assert "iban" in form.errors

    def test_invalid_bic(self):
        form = MandateForm(data=self._data(bic="12"))

        assert "bic" in form.errors

    def test_pdf_without_date(self):
        form = MandateForm(data=self._data(), files={"signed_document": pdf_file()})

        assert "signed_on" in form.errors

    def test_date_without_pdf(self):
        form = MandateForm(data=self._data(signed_on="2027-02-01"))

        assert "signed_document" in form.errors

    def test_non_pdf_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        form = MandateForm(
            data=self._data(signed_on="2027-02-01"),
            files={"signed_document": SimpleUploadedFile("a.pdf", b"hello")},
        )

        assert "signed_document" in form.errors


class SignedDocumentFormTest(TestCase):
    def test_requires_document(self):
        form = SignedDocumentForm(data={"signed_on": ""})

        assert "signed_document" in form.errors

    def test_valid(self):
        form = SignedDocumentForm(
            data={"signed_on": "2027-02-01"}, files={"signed_document": pdf_file()}
        )

        assert form.is_valid(), form.errors
