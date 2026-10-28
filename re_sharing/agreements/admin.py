from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Agreement
from .models import AgreementKind
from .models import Collection
from .models import CollectionRun
from .models import SepaMandate
from .models import SyncState
from .models import UnmatchedReturn


@admin.register(AgreementKind)
class AgreementKindAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "form_type",
        "organization_group",
        "billing_interval",
        "is_active",
        "accepting_applications",
    ]
    list_filter = ["is_active", "accepting_applications", "billing_interval"]
    filter_horizontal = ["accesses"]


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
