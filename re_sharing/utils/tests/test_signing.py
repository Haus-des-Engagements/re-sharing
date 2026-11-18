from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils import signing
from re_sharing.utils.signing import Signature
from re_sharing.utils.signing import SignatureFields
from re_sharing.utils.signing import append_signature_page
from re_sharing.utils.tests.helpers import data_url
from re_sharing.utils.tests.helpers import pdf_bytes
from re_sharing.utils.tests.helpers import png_bytes

BERLIN = ZoneInfo("Europe/Berlin")
PARTY = "Example Organization"


class UploadOrSignForm(SignatureFields):
    upload_field = "document"

    document = forms.FileField(required=False)


def _form(data=None, files=None, signing_for=PARTY):
    return UploadOrSignForm(data=data or {}, files=files, signing_for=signing_for)


class TestSignatureFields:
    def test_fields_only_when_signing_is_offered(self):
        assert "signature_image" not in _form(signing_for=None).fields
        form = _form()
        assert "signature_name" in form.fields
        assert PARTY in form.fields["signature_image"].help_text

    def test_name_and_drawing_accepted(self):
        image = png_bytes()
        form = _form(
            {"signature_name": "Ada Example", "signature_image": data_url(image)}
        )

        assert form.is_valid(), form.errors
        assert form.signature == Signature(name="Ada Example", image=image)

    def test_no_signature_is_valid_and_none(self):
        form = _form()

        assert form.is_valid()
        assert form.signature is None

    def test_form_without_signing_ignores_posted_signature(self):
        form = _form(
            {"signature_name": "Ada", "signature_image": data_url(png_bytes())},
            signing_for=None,
        )

        assert form.is_valid()
        assert form.signature is None

    def test_drawing_without_name_refused(self):
        form = _form({"signature_image": data_url(png_bytes())})

        assert not form.is_valid()
        assert "signature_name" in form.errors
        assert form.signature is None

    def test_name_without_drawing_refused(self):
        form = _form({"signature_name": "Ada Example"})

        assert not form.is_valid()
        assert "signature_image" in form.errors

    def test_name_longer_than_100_characters_refused(self):
        form = _form(
            {"signature_name": "A" * 101, "signature_image": data_url(png_bytes())}
        )

        assert not form.is_valid()
        assert "signature_name" in form.errors

    @pytest.mark.parametrize(
        "value",
        [
            "not a data url",
            "data:image/png;base64,###not-base64###",
            data_url(b"plain text, not an image"),
            data_url(png_bytes(), mime="image/jpeg"),
        ],
    )
    def test_unreadable_drawing_refused(self, value):
        form = _form({"signature_name": "Ada Example", "signature_image": value})

        assert not form.is_valid()
        assert "signature_image" in form.errors

    def test_jpeg_refused(self):
        output = BytesIO()
        Image.new("RGB", (40, 20)).save(output, format="JPEG")
        form = _form(
            {"signature_name": "Ada", "signature_image": data_url(output.getvalue())}
        )

        assert not form.is_valid()

    def test_drawing_over_200_kb_refused(self):
        too_large = png_bytes() + b"\0" * (signing.MAX_IMAGE_BYTES + 1)
        form = _form({"signature_name": "Ada", "signature_image": data_url(too_large)})

        assert not form.is_valid()
        assert "signature_image" in form.errors

    def test_oversized_canvas_refused(self):
        huge = png_bytes(size=(signing.MAX_IMAGE_SIDE + 1, 10))
        form = _form({"signature_name": "Ada", "signature_image": data_url(huge)})

        assert not form.is_valid()

    def test_drawing_together_with_upload_refused(self):
        upload = SimpleUploadedFile("signed.pdf", pdf_bytes())
        form = _form(
            {"signature_name": "Ada", "signature_image": data_url(png_bytes())},
            files={"document": upload},
        )

        assert not form.is_valid()
        assert form.non_field_errors()

    def test_drawing_is_not_rendered_again(self):
        url = data_url(png_bytes())
        form = _form({"signature_image": url})

        html = str(form["signature_image"])

        assert url not in html
        assert "<canvas" in html
        assert "signature_pad" in html


@pytest.mark.django_db()
class TestAppendSignaturePage:
    def _sign(self, pdf, **kwargs):
        user = kwargs.pop("user", None) or UserFactory(email="ada@example.org")
        values = {
            "document_name": "Membership contract",
            "on_behalf_of": PARTY,
            "function": "Board",
            "user": user,
            "signed_at": datetime(2026, 11, 17, 14, 5, tzinfo=BERLIN),
        } | kwargs
        return append_signature_page(
            pdf, Signature(name="Ada Example", image=png_bytes()), **values
        )

    def test_appends_one_page_after_the_source(self):
        result = PdfReader(BytesIO(self._sign(pdf_bytes(pages=3))))

        expected_pages = 4
        assert len(result.pages) == expected_pages
        for number in range(3):
            assert f"Source page {number + 1}" in result.pages[number].extract_text()

    def test_page_names_signer_party_and_time(self):
        result = PdfReader(BytesIO(self._sign(pdf_bytes())))

        text = result.pages[-1].extract_text()
        for expected in (
            "Membership contract",
            PARTY,
            "Ada Example",
            "Board",
            "ada@example.org",
            "17.11.2026, 14:05",
        ):
            assert expected in text
        assert "Source page" not in text

    def test_time_is_shown_in_berlin(self):
        utc = datetime(2026, 7, 1, 10, 0, tzinfo=ZoneInfo("UTC"))

        result = PdfReader(BytesIO(self._sign(pdf_bytes(), signed_at=utc)))

        assert "01.07.2026, 12:00" in result.pages[-1].extract_text()

    def test_page_contains_the_drawing(self):
        result = PdfReader(BytesIO(self._sign(pdf_bytes())))

        assert len(result.pages[-1].images) == 1

    def test_signing_again_appends_a_further_page(self):
        once = self._sign(pdf_bytes(pages=2))

        twice = self._sign(once, on_behalf_of="Example Operator", function="Director")

        result = PdfReader(BytesIO(twice))
        expected_pages = 4
        assert len(result.pages) == expected_pages
        assert PARTY in result.pages[2].extract_text()
        assert "Example Operator" in result.pages[3].extract_text()

    def test_long_values_are_wrapped(self):
        party = "Organization " + "with a very long name " * 12

        result = PdfReader(BytesIO(self._sign(pdf_bytes(), on_behalf_of=party)))

        text = " ".join(result.pages[-1].extract_text().split())
        assert party.strip() in text

    def test_form_fields_of_the_source_are_kept(self):
        output = BytesIO()
        pdf = canvas.Canvas(output)
        pdf.acroForm.textfield(name="amount", x=50, y=700, width=200, value="80,00")
        pdf.showPage()
        pdf.save()

        result = PdfReader(BytesIO(self._sign(output.getvalue())))

        assert result.get_fields()["amount"]["/V"] == "80,00"
