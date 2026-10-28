import re
from decimal import Decimal

from django import forms
from django.utils.formats import localize
from django.utils.translation import gettext_lazy as _

from re_sharing.organizations.models import Organization
from re_sharing.organizations.models import validate_is_pdf

from .fields import add_detail_fields
from .fields import details_from
from .iban import normalize_iban
from .iban import validate_iban
from .models import Agreement

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
    """Common agreement data plus the kind's active application fields, whose
    answers are stored in ``Agreement.details``."""

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

    leading_fields: tuple[str, ...] = ()
    enforce_minimum = True
    trailing_fields: tuple[str, ...] = ("signed_document", "signed_on")

    def __init__(self, *args, kind, details=None, **kwargs):
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
        help_text = _("Charged %(interval)s.") % {"interval": interval}
        if kind.minimum_amount is not None:
            help_text += " " + _("At least %(minimum)s €.") % {
                "minimum": localize(kind.minimum_amount)
            }
            if self.enforce_minimum:
                self.fields["amount"].widget.attrs["min"] = kind.minimum_amount
        self.fields["amount"].help_text = help_text
        self.detail_field_names = add_detail_fields(self, kind, details=details)
        core = [
            "start_date",
            "end_date",
            "amount",
            "deposit_amount",
            "contact_person_function",
        ]
        self.order_fields(
            [
                *self.leading_fields,
                *core,
                *self.detail_field_names,
                *self.trailing_fields,
            ]
        )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end <= start:
            self.add_error("end_date", _("The end date must be after the start."))
        return cleaned

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        minimum = self.kind.minimum_amount
        if self.enforce_minimum and minimum is not None and amount < minimum:
            raise forms.ValidationError(
                _("The amount must be at least %(minimum)s €.")
                % {"minimum": localize(minimum)}
            )
        return amount

    def details(self) -> dict:
        return details_from(self, self.kind)


class ManagerAgreementForm(ApplicationForm):
    """A manager enters an agreement: a paper application or an existing one."""

    enforce_minimum = False

    STATUS_CHOICES = [
        (Agreement.Status.SUBMITTED, _("Submitted, decision pending")),
        (Agreement.Status.ACTIVE, _("Active, already agreed")),
    ]

    organization = forms.ModelChoiceField(
        label=_("Organization"),
        queryset=Organization.objects.filter(
            status=Organization.Status.CONFIRMED
        ).order_by("name"),
    )
    status = forms.TypedChoiceField(
        label=_("Status"), choices=STATUS_CHOICES, coerce=int
    )
    decided_at = forms.DateField(
        label=_("Date of the board decision"),
        widget=DATE_INPUT,
        required=False,
        help_text=_("Active agreements only. Leave empty for today."),
    )
    notes = forms.CharField(
        label=_("Internal notes"),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    leading_fields = ("organization", "status", "decided_at")
    trailing_fields = ("signed_document", "signed_on", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["contact_person_function"]
        field.label = _("Function of the contact person")
        field.required = False


class ManagerAgreementEditForm(ApplicationForm):
    """Edits the data of an agreement; status, kind and organization stay."""

    enforce_minimum = False

    notes = forms.CharField(
        label=_("Internal notes"),
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )

    trailing_fields = ("notes",)

    def __init__(self, *args, agreement, **kwargs):
        kwargs.setdefault(
            "initial",
            {
                "start_date": agreement.start_date,
                "end_date": agreement.end_date,
                "amount": agreement.amount,
                "deposit_amount": agreement.deposit_amount,
                "contact_person_function": agreement.contact_person_function,
                "notes": agreement.notes,
            },
        )
        super().__init__(
            *args, kind=agreement.kind, details=agreement.details, **kwargs
        )
        del self.fields["signed_document"]
        del self.fields["signed_on"]
        field = self.fields["contact_person_function"]
        field.label = _("Function of the contact person")
        field.required = False


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
