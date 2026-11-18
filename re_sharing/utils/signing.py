"""Online signing: the form fields for a typed name and a drawn signature,
and the signature page appended to the signed PDF. Nothing but the PDF is
kept. The page's text is German, like the documents it follows."""

import base64
import binascii
from dataclasses import dataclass
from io import BytesIO

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image
from pypdf import PdfReader
from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

DATA_URL_PREFIX = "data:image/png;base64,"
MAX_IMAGE_BYTES = 200 * 1024
MAX_IMAGE_SIDE = 4000
NAME_MAX_LENGTH = 100


@dataclass(frozen=True)
class Signature:
    name: str
    image: bytes


# =============================================================================
# Form fields
# =============================================================================


class SignaturePadWidget(forms.Widget):
    """A canvas to draw on; the drawing is posted as PNG data URL."""

    template_name = "utils/signature_pad.html"

    def format_value(self, value):
        # A drawing is never shown again, so a signature is always made on
        # the values that are finally submitted.
        return None


class SignatureImageField(forms.Field):
    widget = SignaturePadWidget
    default_error_messages = {
        "invalid": _("The signature could not be read. Please draw it again."),
        "too_large": _("The signature is too large. Please draw it again."),
    }

    def to_python(self, value) -> bytes | None:
        if not value:
            return None
        if not value.startswith(DATA_URL_PREFIX):
            raise forms.ValidationError(self.error_messages["invalid"])
        try:
            content = base64.b64decode(
                value.removeprefix(DATA_URL_PREFIX), validate=True
            )
        except binascii.Error as error:
            raise forms.ValidationError(self.error_messages["invalid"]) from error
        if len(content) > MAX_IMAGE_BYTES:
            raise forms.ValidationError(self.error_messages["too_large"])
        try:
            with Image.open(BytesIO(content), formats=["PNG"]) as image:
                width, height = image.size
                image.verify()
        except (OSError, SyntaxError, ValueError) as error:
            raise forms.ValidationError(self.error_messages["invalid"]) from error
        if max(width, height) > MAX_IMAGE_SIDE:
            raise forms.ValidationError(self.error_messages["too_large"])
        return content


class SignatureFields(forms.Form):
    """Adds a typed name and a drawn signature, given together or not at all,
    when the form is created with ``signing_for``, the party signed for.

    ``upload_field`` names the file field that takes a hand-signed PDF
    instead; only one of the two is accepted.
    """

    upload_field: str | None = None

    def __init__(self, *args, signing_for=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not signing_for:
            return
        self.fields["signature_name"] = forms.CharField(
            label=_("Sign online: your full name"),
            max_length=NAME_MAX_LENGTH,
            required=False,
        )
        self.fields["signature_image"] = SignatureImageField(
            label=_("Your signature"),
            required=False,
            help_text=_(
                "Draw with the mouse or your finger. By signing I confirm that I "
                "have read the document and may sign it on behalf of %(party)s."
            )
            % {"party": signing_for},
        )

    def clean(self):
        cleaned = super().clean()
        if "signature_image" not in self.fields:
            return cleaned
        name = cleaned.get("signature_name")
        image = cleaned.get("signature_image")
        if image and not name:
            self.add_error("signature_name", _("Type your name to sign."))
        if name and not image and "signature_image" not in self.errors:
            self.add_error("signature_image", _("Draw your signature."))
        if image and self.upload_field and cleaned.get(self.upload_field):
            self.add_error(
                None, _("Either upload a signed PDF or sign online, not both.")
            )
        return cleaned

    @property
    def signature(self) -> Signature | None:
        """The signature of a valid form, or None when it was not signed."""
        if not self.is_valid():
            return None
        name = self.cleaned_data.get("signature_name")
        image = self.cleaned_data.get("signature_image")
        return Signature(name=name, image=image) if name and image else None


# =============================================================================
# Signature page
# =============================================================================

MARGIN = 20 * mm
WIDTH, HEIGHT = A4
TEXT_WIDTH = WIDTH - 2 * MARGIN
LABEL_WIDTH = 45 * mm
IMAGE_HEIGHT = 35 * mm


class _Page:
    def __init__(self, pdf):
        self.pdf = pdf
        self.y = HEIGHT - MARGIN

    def text(self, value, *, size=10, bold=False, gap=4):
        font = "Helvetica-Bold" if bold else "Helvetica"
        self.pdf.setFont(font, size)
        for line in simpleSplit(value, font, size, TEXT_WIDTH):
            self.y -= size * 1.3
            self.pdf.drawString(MARGIN, self.y, line)
        self.y -= gap

    def row(self, label, value):
        self.y -= 6
        self.pdf.setFont("Helvetica", 9)
        self.pdf.drawString(MARGIN, self.y - 13, label)
        self.pdf.setFont("Helvetica", 11)
        lines = simpleSplit(value, "Helvetica", 11, TEXT_WIDTH - LABEL_WIDTH)
        for line in lines or [""]:
            self.y -= 14
            self.pdf.drawString(MARGIN + LABEL_WIDTH, self.y, line)

    def image(self, content: bytes):
        self.y -= IMAGE_HEIGHT + 10
        self.pdf.drawImage(
            ImageReader(BytesIO(content)),
            MARGIN,
            self.y,
            width=TEXT_WIDTH / 2,
            height=IMAGE_HEIGHT,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto",
        )
        self.pdf.setLineWidth(0.6)
        self.pdf.line(MARGIN, self.y - 2, MARGIN + TEXT_WIDTH / 2, self.y - 2)
        self.y -= 2


def _signature_page(image: bytes, head, rows, note: str) -> bytes:
    """``head`` rows, the drawing, ``rows`` and a closing note."""
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    page = _Page(pdf)
    page.text("Elektronische Unterschrift", size=16, bold=True, gap=10)
    for label, value in head:
        page.row(label, value)
    page.image(image)
    for label, value in rows:
        page.row(label, value)
    page.y -= 16
    page.text(note, size=9)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def append_signature_page(  # noqa: PLR0913
    pdf: bytes,
    signature: Signature,
    *,
    document_name: str,
    on_behalf_of: str,
    function: str,
    user,
    signed_at=None,
) -> bytes:
    """``pdf`` followed by one page with the signature. The source pages are
    copied unchanged; signing again appends a further page."""
    signed_at = timezone.localtime(signed_at or timezone.now())
    page = _signature_page(
        signature.image,
        head=[("Dokument", document_name), ("Unterzeichnet für", on_behalf_of)],
        rows=[
            ("Name", signature.name),
            ("Funktion", function or "-"),
            ("Datum und Uhrzeit", f"{signed_at:%d.%m.%Y, %H:%M} Uhr"),
            ("Benutzerkonto", user.email),
        ],
        note=(
            "Online unterzeichnet. Mit der Unterschrift wurde bestätigt, das "
            f"Dokument gelesen zu haben und es für {on_behalf_of} unterzeichnen "
            "zu dürfen."
        ),
    )
    writer = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    writer.add_page(PdfReader(BytesIO(page)).pages[0])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
