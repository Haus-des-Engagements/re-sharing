from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from pypdf.errors import PdfReadError

from . import documents
from . import selectors
from .models import Agreement
from .models import AgreementKind
from .models import AgreementKindField
from .models import Collection
from .models import CollectionRun
from .models import SepaMandate
from .models import SyncState
from .models import UnmatchedReturn


class AgreementKindFieldForm(forms.ModelForm):
    class Meta:
        model = AgreementKindField
        fields = [
            "order",
            "key",
            "label",
            "field_type",
            "required",
            "help_text",
            "choices",
            "min_value",
            "is_active",
        ]
        widgets = {"choices": forms.Textarea(attrs={"rows": 2, "cols": 20})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["key"].disabled = True


class AgreementKindFieldFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.deleted_forms:
            field = form.instance
            if field.pk and selectors.field_has_answers(field):
                raise ValidationError(
                    _(
                        "The field %(label)s has answers and cannot be deleted. "
                        "Deactivate it instead."
                    )
                    % {"label": field.label}
                )


class AgreementKindFieldInline(admin.TabularInline):
    model = AgreementKindField
    form = AgreementKindFieldForm
    formset = AgreementKindFieldFormSet
    extra = 0


@admin.register(AgreementKind)
class AgreementKindAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "organization_group",
        "billing_interval",
        "is_active",
        "accepting_applications",
    ]
    list_filter = ["is_active", "accepting_applications", "billing_interval"]
    filter_horizontal = ["accesses"]
    inlines = [AgreementKindFieldInline]
    readonly_fields = ["template_fields"]

    @admin.display(description=_("Fields of the contract template"))
    def template_fields(self, obj):
        if obj is None or not obj.contract_template:
            return _("No contract template uploaded.")
        try:
            names = documents.template_field_names(obj)
        except PdfReadError:
            return _("The contract template could not be read.")
        if not names:
            return _("The contract template has no form fields.")
        return format_html_join(
            mark_safe("<br>"),  # noqa: S308
            "<code>{}</code>: {}",
            (
                (
                    name,
                    _("filled")
                    if documents.is_filled_field(obj, name)
                    else _("left empty"),
                )
                for name in names
            ),
        )

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.agreements_of_kind.exists():
            return False
        return super().has_delete_permission(request, obj)


class SepaMandateInline(admin.StackedInline):
    model = SepaMandate
    extra = 0
    fields = [
        "reference",
        "account_holder",
        "iban",
        "bic",
        "bank_name",
        "signed_on",
        "signed_document",
        "revoked_on",
    ]


class CollectionInline(admin.TabularInline):
    model = Collection
    extra = 0
    fields = [
        "kind",
        "period_start",
        "period_end",
        "due_date",
        "amount",
        "status",
        "reference",
    ]
    readonly_fields = ["reference"]
    show_change_link = True


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    """Creating agreements here never runs the approval: no emails, groups or
    codes. Used to enter agreements that already exist on paper."""

    list_display = [
        "organization",
        "kind",
        "status",
        "amount",
        "start_date",
        "end_date",
        "group_present",
    ]
    list_filter = ["status", "kind"]
    search_fields = ["organization__name"]
    autocomplete_fields = ["organization", "permanent_code"]
    readonly_fields = ["group_present", "decided_by"]
    inlines = [SepaMandateInline, CollectionInline]

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not selectors.agreement_can_be_deleted(obj):
            return False
        return super().has_delete_permission(request, obj)

    @admin.display(description=_("Group of the kind present"), boolean=True)
    def group_present(self, obj):
        if not obj.pk:
            return None
        return obj.organization.organization_groups.filter(
            id=obj.kind.organization_group_id
        ).exists()


@admin.register(SepaMandate)
class SepaMandateAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "agreement",
        "account_holder",
        "masked_iban",
        "signed_on",
        "revoked_on",
    ]
    list_filter = ["revoked_on"]
    search_fields = ["reference", "account_holder", "agreement__organization__name"]

    @admin.display(description=_("IBAN"))
    def masked_iban(self, obj):
        return obj.masked_iban


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "agreement",
        "kind",
        "period_start",
        "due_date",
        "amount",
        "status",
    ]
    list_filter = ["status", "kind", "agreement__kind"]
    search_fields = ["reference", "agreement__organization__name", "invoice_number"]
    raw_id_fields = ["agreement", "mandate", "run"]


@admin.register(CollectionRun)
class CollectionRunAdmin(admin.ModelAdmin):
    list_display = ["collection_date", "count", "total_amount", "uploaded_at"]
    readonly_fields = ["created_by", "uploaded_by"]


@admin.register(UnmatchedReturn)
class UnmatchedReturnAdmin(admin.ModelAdmin):
    list_display = ["booked_on", "amount", "text", "resolved"]
    list_filter = ["resolved"]


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ["key", "synced_at"]
