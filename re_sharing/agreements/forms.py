import re
from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from re_sharing.organizations.models import validate_is_pdf

from .iban import normalize_iban
from .iban import validate_iban
from .models import AgreementKind

BIC_PATTERN = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")
DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class SignedDocumentFields(forms.Form):
    """A signed PDF and its signing date, given together or not at all."""

    document_required = False

    signed_document = forms.FileField(
        label=_("Signed PDF"), required=False, validators=[validate_is_pdf]
    )
    signed_on = forms.DateField(label=_("Signed on"), required=False, widget=DATE_INPUT)

    def clean(self):
        cleaned = super().clean()
        document = cleaned.get("signed_document")
        signed_on = cleaned.get("signed_on")
        if document and not signed_on:
            self.add_error("signed_on", _("Enter the date of the signature."))
        if signed_on and not document:
            self.add_error("signed_document", _("Upload the signed PDF."))
        if self.document_required and not document:
            self.add_error("signed_document", _("Upload the signed PDF."))
        return cleaned


class SignedDocumentForm(SignedDocumentFields):
    document_required = True


class MandateForm(SignedDocumentFields):
    account_holder = forms.CharField(label=_("Account holder"), max_length=70)
    iban = forms.CharField(label=_("IBAN"), max_length=42)
    bic = forms.CharField(label=_("BIC"), max_length=11, required=False)
    bank_name = forms.CharField(label=_("Bank"), max_length=100, required=False)

    field_order = [
        "account_holder",
        "iban",
        "bic",
        "bank_name",
        "signed_document",
        "signed_on",
    ]

    def clean_iban(self):
        iban = normalize_iban(self.cleaned_data["iban"])
        validate_iban(iban)
        return iban

    def clean_bic(self):
        bic = normalize_iban(self.cleaned_data.get("bic", ""))
        if bic and not BIC_PATTERN.match(bic):
            raise forms.ValidationError(_("This is not a valid BIC."))
        return bic


class RevokeMandateForm(forms.Form):
    revoked_on = forms.DateField(label=_("Revoked on"), widget=DATE_INPUT)


class ApplicationForm(SignedDocumentFields):
    """Base application. Subclasses add the kind-specific ``DETAIL_FIELDS``,
    which are stored in ``Agreement.details``."""

    DETAIL_FIELDS: tuple[str, ...] = ()

    start_date = forms.DateField(label=_("Start date"), widget=DATE_INPUT)
    end_date = forms.DateField(label=_("End date"), widget=DATE_INPUT, required=False)
    amount = forms.DecimalField(
        label=_("Amount per period in €"),
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    deposit_amount = forms.DecimalField(
        label=_("Deposit in €"),
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )
    contact_person_function = forms.CharField(
        label=_("Your function in the organization"), max_length=100
    )

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        if kind.requires_deposit:
            self.fields["deposit_amount"].required = True
        else:
            del self.fields["deposit_amount"]
        if kind.requires_end_date:
            self.fields["end_date"].required = True
        else:
            del self.fields["end_date"]
        interval = kind.get_billing_interval_display().lower()
        self.fields["amount"].help_text = _("Charged %(interval)s.") % {
            "interval": interval
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end <= start:
            self.add_error("end_date", _("The end date must be after the start."))
        return cleaned

    def details(self) -> dict:
        details = {}
        for name in self.DETAIL_FIELDS:
            value = self.cleaned_data.get(name)
            if isinstance(value, Decimal):
                value = str(value)
            details[name] = value
        return details


class MembershipApplicationForm(ApplicationForm):
    pass


class CoworkingApplicationForm(ApplicationForm):
    DETAIL_FIELDS = ("desks", "hours_per_week")

    desks = forms.IntegerField(label=_("Desks"), min_value=1)
    hours_per_week = forms.IntegerField(label=_("Hours per week"), min_value=1)


class OfficeApplicationForm(ApplicationForm):
    DETAIL_FIELDS = ("room",)

    room = forms.CharField(label=_("Room"), max_length=100)


class CellarApplicationForm(ApplicationForm):
    DETAIL_FIELDS = ("area_m2",)

    area_m2 = forms.DecimalField(
        label=_("Area in m²"), max_digits=6, decimal_places=2, min_value=Decimal(1)
    )


APPLICATION_FORMS = {
    AgreementKind.FormType.MEMBERSHIP: MembershipApplicationForm,
    AgreementKind.FormType.COWORKING: CoworkingApplicationForm,
    AgreementKind.FormType.OFFICE: OfficeApplicationForm,
    AgreementKind.FormType.CELLAR: CellarApplicationForm,
}


def application_form_class(kind) -> type[ApplicationForm]:
    return APPLICATION_FORMS[kind.form_type]


def detail_items(agreement) -> list[tuple[str, object]]:
    """The kind-specific details with the labels of their form fields."""
    form_class = application_form_class(agreement.kind)
    fields = form_class.base_fields
    return [
        (fields[name].label, agreement.details.get(name))
        for name in form_class.DETAIL_FIELDS
        if name in agreement.details
    ]


class DecisionForm(forms.Form):
    decided_at = forms.DateField(
        label=_("Date of the board decision"), widget=DATE_INPUT
    )


class EndAgreementForm(forms.Form):
    end_date = forms.DateField(
        label=_("End date"),
        widget=DATE_INPUT,
        required=False,
        help_text=_("Leave empty to end today or on the agreed end date."),
    )


class CollectionNoteForm(forms.Form):
    note = forms.CharField(label=_("Note"), widget=forms.Textarea(attrs={"rows": 2}))


class BuildRunForm(forms.Form):
    collection_date = forms.DateField(label=_("Collection date"), widget=DATE_INPUT)
