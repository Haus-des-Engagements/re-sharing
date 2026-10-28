"""Documents prefilled from agreement data: the kind's fillable contract
template and the generated SEPA mandate. Both are rendered on request and
never stored. Their text is German, like the contracts themselves."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from pypdf import PdfReader
from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from .fields import to_python

CHECKBOX_FIELDS = frozenset({"represented_by_person"})


def format_money(value) -> str:
    if value is None:
        return ""
    return (
        f"{Decimal(value):,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    )


def format_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def _format_detail(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, Decimal):
        return str(value).replace(".", ",")
    if isinstance(value, date):
        return format_date(value)
    return str(value)


def organization_address(organization) -> str:
    street = organization.street_and_housenb
    return f"{street}, {organization.zip_code} {organization.city}"


# =============================================================================
# Contract template
# =============================================================================


def _read_template(kind) -> bytes:
    with kind.contract_template.open("rb") as template:
        return template.read()


def template_field_names(kind) -> list[str]:
    """The form field names of the kind's template, in document order."""
    if not kind.contract_template:
        return []
    fields = PdfReader(BytesIO(_read_template(kind))).get_fields() or {}
    return list(fields)


def contract_values(agreement, person) -> dict[str, str]:
    """Values by field name. ``person`` is the representative, or None."""
    organization = agreement.organization
    values = {
        "organization_name": organization.name,
        "organization_address": organization_address(organization),
        "organization_phone": organization.phone,
        "organization_email": organization.email,
        "organization_website": organization.website,
        "represented_by_person": True,
        "representative_name": person.get_full_name() if person else "",
        "representative_function": agreement.contact_person_function,
        "representative_email": person.email if person else "",
        "amount": format_money(agreement.amount),
        "start_date": format_date(agreement.start_date),
        "end_date": format_date(agreement.end_date),
        "deposit_amount": format_money(agreement.deposit_amount),
        "kind_name": agreement.kind.name,
    }
    details = agreement.details or {}
    for definition in agreement.kind.fields_of_kind.all():
        stored = details.get(definition.key)
        values[f"detail_{definition.key}"] = _format_detail(
            to_python(definition, stored)
        )
    return values


def filled_field_names() -> frozenset[str]:
    """Names the system fills, apart from ``detail_<key>``."""
    return frozenset(
        {
            "organization_name",
            "organization_address",
            "organization_phone",
            "organization_email",
            "organization_website",
            "represented_by_person",
            "representative_name",
            "representative_function",
            "representative_email",
            "amount",
            "start_date",
            "end_date",
            "deposit_amount",
            "kind_name",
        }
    )


def is_filled_field(kind, name: str) -> bool:
    if name in filled_field_names():
        return True
    if name.startswith("detail_"):
        key = name.removeprefix("detail_")
        return kind.fields_of_kind.filter(key=key).exists()
    return False


def _checked_state(field) -> str:
    states = [state for state in field.get("/_States_", []) if state != "/Off"]
    return states[0] if states else "/Yes"


def prefilled_contract(agreement, person) -> bytes:
    """The kind's template with its fields filled; fields stay editable."""
    reader = PdfReader(BytesIO(_read_template(agreement.kind)))
    fields = reader.get_fields() or {}
    values = {}
    for name, value in contract_values(agreement, person).items():
        if name not in fields:
            continue
        if name in CHECKBOX_FIELDS:
            values[name] = _checked_state(fields[name]) if value else "/Off"
        else:
            values[name] = value
    writer = PdfWriter(clone_from=reader)
    if values:
        writer.update_page_form_field_values(None, values, auto_regenerate=False)
    writer.set_need_appearances_writer(True)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


# =============================================================================
# SEPA mandate
# =============================================================================

MARGIN = 20 * mm
WIDTH, HEIGHT = A4
TEXT_WIDTH = WIDTH - 2 * MARGIN


def _grouped_iban(iban: str) -> str:
    return " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))


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
        self.y -= 16
        self.pdf.setFont("Helvetica", 9)
        self.pdf.drawString(MARGIN, self.y, label)
        self.pdf.setFont("Helvetica", 11)
        self.pdf.drawString(MARGIN + 45 * mm, self.y, value)
        self.pdf.setLineWidth(0.4)
        self.pdf.line(MARGIN + 45 * mm, self.y - 3, WIDTH - MARGIN, self.y - 3)

    def signature_lines(self):
        self.y -= 50
        half = TEXT_WIDTH / 2 - 10 * mm
        self.pdf.setLineWidth(0.6)
        self.pdf.line(MARGIN, self.y, MARGIN + half, self.y)
        self.pdf.line(WIDTH - MARGIN - half, self.y, WIDTH - MARGIN, self.y)
        self.pdf.setFont("Helvetica", 9)
        self.pdf.drawString(MARGIN, self.y - 12, "Ort, Datum")
        self.pdf.drawString(WIDTH - MARGIN - half, self.y - 12, "Unterschrift")
        self.pdf.setFont("Helvetica", 8)
        self.pdf.drawString(
            WIDTH - MARGIN - half,
            self.y - 23,
            "kontoinhabende bzw. vertretungsberechtigte Person",
        )


def render_mandate(mandate) -> bytes:
    """One page: creditor, reference, standard wording and debtor data."""
    agreement = mandate.agreement
    organization = agreement.organization
    creditor = settings.SEPA_CREDITOR_NAME
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    pdf.setTitle(f"SEPA-Lastschriftmandat {mandate.reference}")
    page = _Page(pdf)

    page.text("SEPA-Lastschriftmandat", size=16, bold=True, gap=8)
    page.text("für wiederkehrende Zahlungen (SEPA-Basislastschrift)", gap=12)
    page.text("Zahlungsempfänger", size=9, bold=True, gap=0)
    page.text(creditor, gap=0)
    page.text(settings.SEPA_CREDITOR_ADDRESS, gap=0)
    page.text(f"Gläubiger-Identifikationsnummer: {settings.SEPA_CREDITOR_ID}", gap=0)
    page.text(f"Mandatsreferenz: {mandate.reference}", bold=True, gap=0)
    page.text(f"Vereinbarung: {agreement.kind.name}", gap=12)

    page.text(
        f"Ich ermächtige / Wir ermächtigen {creditor}, Zahlungen aus der oben "
        "genannten Vereinbarung von meinem / unserem Konto mittels Lastschrift "
        "einzuziehen. Zugleich weise ich mein / weisen wir unser Kreditinstitut "
        f"an, die von {creditor} auf mein / unser Konto gezogenen Lastschriften "
        "einzulösen. Über Betrag und Termin der Einzüge informieren wir vorab "
        "per E-Mail."
    )
    page.text(
        "Hinweis: Ich kann / Wir können innerhalb von acht Wochen, beginnend mit "
        "dem Belastungsdatum, die Erstattung des belasteten Betrages verlangen. "
        "Es gelten dabei die mit meinem / unserem Kreditinstitut vereinbarten "
        "Bedingungen.",
        gap=12,
    )

    page.text("Zahlungspflichtige/r", size=9, bold=True, gap=0)
    page.row("Organisation", organization.name)
    page.row("Anschrift", organization_address(organization))
    page.row("Kontoinhaber*in", mandate.account_holder)
    page.row("Kreditinstitut", mandate.bank_name)
    page.row("IBAN", _grouped_iban(mandate.iban))
    page.row("BIC", mandate.bic)
    page.signature_lines()

    pdf.showPage()
    pdf.save()
    return output.getvalue()
