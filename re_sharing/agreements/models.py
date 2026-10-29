import re
import uuid
from decimal import Decimal
from pathlib import Path

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.core.exceptions import ValidationError
from django.core.files.utils import validate_file_name
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db.models import CASCADE
from django.db.models import PROTECT
from django.db.models import SET_NULL
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import DateField
from django.db.models import DateTimeField
from django.db.models import DecimalField
from django.db.models import FileField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import JSONField
from django.db.models import ManyToManyField
from django.db.models import PositiveIntegerField
from django.db.models import PositiveSmallIntegerField
from django.db.models import Q
from django.db.models import SlugField
from django.db.models import TextChoices
from django.db.models import TextField
from django.db.models import UniqueConstraint
from django.db.models import UUIDField
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from django_extensions.db.fields import AutoSlugField
from tinymce.models import HTMLField

from re_sharing.agreements.iban import normalize_iban
from re_sharing.agreements.iban import validate_iban
from re_sharing.organizations.models import select_private_storage
from re_sharing.organizations.models import validate_is_pdf
from re_sharing.utils.models import TimeStampedModel

MONEY = {"max_digits": 10, "decimal_places": 2}
RETURN_INVOICE_DUE_DAYS = 14


def _upload_path(folder, suffix, instance, filename):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    extension = Path(filename).suffix
    return str(Path(folder) / f"{timestamp}_{instance.uuid}_{suffix}{extension}")


def agreement_document_upload_to(instance, filename):
    return _upload_path("agreements", "contract", instance, filename)


def kind_template_upload_to(instance, filename):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return str(Path("agreement_templates") / f"{timestamp}_{instance.slug}.pdf")


def mandate_document_upload_to(instance, filename):
    """``mandates/<readable name>``: downloads from private storage carry the
    stored name. References are unique; storage suffixes the rare repeat."""
    name = instance.document_filename(instance.signed_on or timezone.localdate())
    return str(Path("mandates") / name)


class ReadableNameFileField(FileField):
    """Stores files under the name ``upload_to`` returns, spaces included,
    instead of the storage's ASCII-safe variant with underscores."""

    def generate_filename(self, instance, filename):
        return validate_file_name(
            self.upload_to(instance, filename), allow_relative_path=True
        )


FILENAME_UNSAFE = re.compile(r'[\\/:*?"<>|.\x00-\x1f]+')
FILENAME_PART_LENGTH = 80


def filename_part(text: str) -> str:
    """``text`` usable in a file name: without dots and invalid characters."""
    cleaned = " ".join(FILENAME_UNSAFE.sub("", " ".join(text.split())).split())
    return cleaned[:FILENAME_PART_LENGTH].strip()


def run_xml_upload_to(instance, filename):
    return _upload_path("collection_runs", "sepa", instance, filename)


class AgreementKind(TimeStampedModel):
    class BillingInterval(TextChoices):
        YEARLY = "yearly", _("Yearly")
        MONTHLY = "monthly", _("Monthly")

    class NotificationMode(TextChoices):
        EACH_COLLECTION = "each_collection", _("Before each collection")
        ONCE_AT_APPROVAL = "once_at_approval", _("Once with the approval")

    name = CharField(_("Name"), max_length=160)
    slug = AutoSlugField(populate_from="name", unique=True, editable=True)
    organization_group = ForeignKey(
        "organizations.OrganizationGroup",
        verbose_name=_("Organization group"),
        on_delete=PROTECT,
        related_name="agreementkinds_of_organizationgroup",
        related_query_name="agreementkind_of_organizationgroup",
        help_text=_("Granted while an agreement of this kind is active."),
    )
    billing_interval = CharField(
        _("Billing interval"), max_length=10, choices=BillingInterval.choices
    )
    requires_deposit = BooleanField(_("Requires a deposit"), default=False)
    notice_period_weeks = PositiveSmallIntegerField(
        _("Notice period in weeks"), null=True, blank=True
    )
    requires_end_date = BooleanField(_("Requires an end date"), default=False)
    minimum_amount = DecimalField(
        _("Minimum amount per period"),
        null=True,
        blank=True,
        help_text=_(
            "Lowest amount applicants can enter. Managers may enter less. Leave "
            "empty for no minimum."
        ),
        **MONEY,
    )
    accesses = ManyToManyField(
        "resources.Access",
        verbose_name=_("Accesses of the permanent code"),
        related_name="agreementkinds_of_access",
        related_query_name="agreementkind_of_access",
        blank=True,
        help_text=_("Leave empty when the kind grants no entrance code."),
    )
    notification_mode = CharField(
        _("Pre-notification"),
        max_length=20,
        choices=NotificationMode.choices,
        default=NotificationMode.EACH_COLLECTION,
    )
    collection_day = PositiveSmallIntegerField(
        _("Collection day"),
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text=_("Day of the month on which fees are due (1 to 28)."),
    )
    collection_month = PositiveSmallIntegerField(
        _("Collection month"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_("Yearly kinds only: month of the yearly collection date."),
    )
    intro_text = HTMLField(
        _("Intro text"),
        blank=True,
        help_text=_(
            "Shown on the application page, for example what applicants should "
            "know before applying. The contract itself is uploaded as contract "
            "template."
        ),
    )
    contract_template = FileField(
        _("Contract template"),
        upload_to=kind_template_upload_to,
        validators=[validate_is_pdf],
        storage=select_private_storage,
        null=True,
        blank=True,
        help_text=_(
            "Fillable PDF. Its form fields are filled by name with the "
            "agreement's data when an applicant downloads the contract."
        ),
    )
    is_active = BooleanField(_("Active"), default=True)
    accepting_applications = BooleanField(_("Accepting applications"), default=True)

    class Meta:
        verbose_name = _("Agreement kind")
        verbose_name_plural = _("Agreement kinds")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        is_yearly = self.billing_interval == self.BillingInterval.YEARLY
        if is_yearly and not self.collection_month:
            raise ValidationError({"collection_month": _("Required for yearly kinds.")})
        if not is_yearly and self.collection_month:
            raise ValidationError(
                {"collection_month": _("Only yearly kinds have a collection month.")}
            )

    @property
    def is_yearly(self):
        return self.billing_interval == self.BillingInterval.YEARLY

    @property
    def active_fields(self):
        return [field for field in self.fields_of_kind.all() if field.is_active]


# Names used by the agreement forms; field keys must not shadow them.
RESERVED_FIELD_KEYS = frozenset(
    {
        "amount",
        "contact_person_function",
        "decided_at",
        "deposit_amount",
        "end_date",
        "notes",
        "organization",
        "signed_document",
        "signed_on",
        "start_date",
        "status",
    }
)


class AgreementKindField(TimeStampedModel):
    """One application field of a kind. Answers are stored in
    ``Agreement.details`` under ``key``."""

    class FieldType(TextChoices):
        TEXT = "text", _("Text")
        INTEGER = "integer", _("Whole number")
        DECIMAL = "decimal", _("Decimal")
        DATE = "date", _("Date")
        CHOICE = "choice", _("Choice")

    NUMBER_TYPES = (FieldType.INTEGER, FieldType.DECIMAL)

    kind = ForeignKey(
        AgreementKind,
        verbose_name=_("Kind"),
        on_delete=CASCADE,
        related_name="fields_of_kind",
        related_query_name="field_of_kind",
    )
    key = SlugField(
        _("Key"),
        max_length=50,
        help_text=_(
            "Name under which answers are stored. Cannot be changed afterwards."
        ),
    )
    label = CharField(_("Label"), max_length=100)
    field_type = CharField(_("Type"), max_length=10, choices=FieldType.choices)
    required = BooleanField(_("Required"), default=True)
    help_text = CharField(_("Help text"), max_length=200, blank=True)
    choices = TextField(
        _("Choices"), blank=True, help_text=_("Choice fields only: one per line.")
    )
    min_value = DecimalField(
        _("Minimum"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Number fields only."),
    )
    order = PositiveSmallIntegerField(_("Order"), default=0)
    is_active = BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Application field")
        verbose_name_plural = _("Application fields")
        ordering = ["order", "id"]
        constraints = [
            UniqueConstraint(
                fields=["kind", "key"],
                name="agreementkindfield_unique_key_per_kind",
                violation_error_message=_("This key is already used by this kind."),
            ),
        ]

    def __str__(self):
        return f"{self.kind} - {self.label}"

    def clean(self):
        super().clean()
        errors = {}
        if self.key in RESERVED_FIELD_KEYS:
            errors["key"] = _("This key is reserved for the agreement itself.")
        is_choice = self.field_type == self.FieldType.CHOICE
        if is_choice and not self.choice_list:
            errors["choices"] = _("Enter at least one choice.")
        if not is_choice and self.choices.strip():
            errors["choices"] = _("Only choice fields have choices.")
        if self.min_value is not None:
            if self.field_type not in self.NUMBER_TYPES:
                errors["min_value"] = _("Only number fields have a minimum.")
            elif (
                self.field_type == self.FieldType.INTEGER
                and self.min_value != self.min_value.to_integral_value()
            ):
                errors["min_value"] = _("Enter a whole number.")
        if errors:
            raise ValidationError(errors)

    @property
    def choice_list(self) -> list[str]:
        return [line.strip() for line in self.choices.splitlines() if line.strip()]


class Agreement(TimeStampedModel):
    class Status(IntegerChoices):
        SUBMITTED = 1, _("Submitted")
        ACTIVE = 2, _("Active")
        REJECTED = 3, _("Rejected")
        ENDED = 4, _("Ended")

    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    history = AuditlogHistoryField()
    organization = ForeignKey(
        "organizations.Organization",
        verbose_name=_("Organization"),
        on_delete=PROTECT,
        related_name="agreements_of_organization",
        related_query_name="agreement_of_organization",
    )
    kind = ForeignKey(
        AgreementKind,
        verbose_name=_("Kind"),
        on_delete=PROTECT,
        related_name="agreements_of_kind",
        related_query_name="agreement_of_kind",
    )
    status = IntegerField(_("Status"), choices=Status.choices, default=Status.SUBMITTED)
    amount = DecimalField(_("Amount per period"), **MONEY)
    deposit_amount = DecimalField(_("Deposit"), null=True, blank=True, **MONEY)
    start_date = DateField(_("Start date"))
    end_date = DateField(_("End date"), null=True, blank=True)
    contact_person_function = CharField(
        _("Function of the contact person"), max_length=100, blank=True
    )
    details = JSONField(_("Kind-specific details"), default=dict, blank=True)
    signed_document = FileField(
        _("Signed contract"),
        upload_to=agreement_document_upload_to,
        validators=[validate_is_pdf],
        storage=select_private_storage,
        null=True,
        blank=True,
    )
    signed_on = DateField(_("Signed on"), null=True, blank=True)
    decided_at = DateField(_("Decided on"), null=True, blank=True)
    decided_by = ForeignKey(
        "users.User",
        verbose_name=_("Decided by"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="decidedagreements_of_user",
        related_query_name="decidedagreement_of_user",
    )
    permanent_code = ForeignKey(
        "resources.PermanentCode",
        verbose_name=_("Permanent code"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="agreements_of_permanentcode",
        related_query_name="agreement_of_permanentcode",
    )
    contact_person = ForeignKey(
        "users.User",
        verbose_name=_("Contact person"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="contactagreements_of_user",
        related_query_name="contactagreement_of_user",
        help_text=_("Applied for the agreement and is named in the contract."),
    )
    notes = TextField(_("Internal notes"), blank=True)

    class Meta:
        verbose_name = pgettext_lazy("agreements", "Agreement")
        verbose_name_plural = _("Agreements")
        ordering = ["-created"]
        constraints = [
            UniqueConstraint(
                fields=["organization", "kind"],
                condition=Q(status__in=[1, 2]),
                name="agreement_one_open_per_organization_and_kind",
                violation_error_message=_(
                    "The organization already has a submitted or active agreement "
                    "of this kind."
                ),
            ),
        ]

    def __str__(self):
        return f"{self.kind} - {self.organization}"

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= Decimal(0):
            raise ValidationError({"amount": _("The amount must be above zero.")})
        if (
            self.kind_id
            and not self.kind.requires_deposit
            and self.deposit_amount is not None
        ):
            raise ValidationError(
                {"deposit_amount": _("This kind of agreement has no deposit.")}
            )

    def get_absolute_url(self):
        return reverse("agreements:show-agreement", args=[str(self.uuid)])

    @property
    def has_complete_signed_document(self):
        return bool(self.signed_document)

    @property
    def active_mandate(self):
        for mandate in self.mandates_of_agreement.all():
            if mandate.is_active:
                return mandate
        return None

    @property
    def open_mandate(self):
        """The mandate that is not revoked, with or without signed PDF."""
        for mandate in self.mandates_of_agreement.all():
            if mandate.revoked_on is None:
                return mandate
        return None


class SepaMandate(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    history = AuditlogHistoryField()
    agreement = ForeignKey(
        Agreement,
        verbose_name=pgettext_lazy("agreements", "Agreement"),
        on_delete=PROTECT,
        related_name="mandates_of_agreement",
        related_query_name="mandate_of_agreement",
    )
    reference = CharField(_("Mandate reference"), max_length=35, unique=True)
    account_holder = CharField(_("Account holder"), max_length=70)
    iban = CharField(_("IBAN"), max_length=34, validators=[validate_iban])
    bic = CharField(_("BIC"), max_length=11, blank=True)
    bank_name = CharField(_("Bank"), max_length=100, blank=True)
    signed_on = DateField(_("Signed on"), null=True, blank=True)
    signed_document = ReadableNameFileField(
        _("Signed mandate"),
        upload_to=mandate_document_upload_to,
        validators=[validate_is_pdf],
        storage=select_private_storage,
        null=True,
        blank=True,
        max_length=255,
    )
    revoked_on = DateField(_("Revoked on"), null=True, blank=True)

    class Meta:
        verbose_name = _("SEPA mandate")
        verbose_name_plural = _("SEPA mandates")
        ordering = ["-created"]
        constraints = [
            UniqueConstraint(
                fields=["agreement"],
                condition=Q(revoked_on__isnull=True),
                name="sepamandate_one_open_per_agreement",
                violation_error_message=_(
                    "This agreement already has a mandate that is not revoked."
                ),
            ),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        self.iban = normalize_iban(self.iban)
        super().save(*args, **kwargs)

    def document_filename(self, on) -> str:
        """``<reference>_SEPA-Lastschriftmandat_<organization>_<date>.pdf``."""
        organization = filename_part(self.agreement.organization.name)
        return (
            f"{self.reference}_SEPA-Lastschriftmandat_"
            f"{organization}_{on:%Y-%m-%d}.pdf"
        )

    @property
    def is_active(self):
        return bool(self.signed_document) and self.revoked_on is None

    @property
    def masked_iban(self):
        if len(self.iban) <= 4:  # noqa: PLR2004
            return self.iban
        return "•" * (len(self.iban) - 4) + self.iban[-4:]

    def get_absolute_url(self):
        return reverse("agreements:show-mandate", args=[str(self.uuid)])


class CollectionRun(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    collection_date = DateField(_("Collection date"))
    xml_file = FileField(
        _("SEPA file"),
        upload_to=run_xml_upload_to,
        storage=select_private_storage,
        null=True,
        blank=True,
    )
    created_by = ForeignKey(
        "users.User",
        verbose_name=_("Created by"),
        on_delete=SET_NULL,
        null=True,
        related_name="createdcollectionruns_of_user",
        related_query_name="createdcollectionrun_of_user",
    )
    uploaded_at = DateTimeField(_("Uploaded at"), null=True, blank=True)
    uploaded_by = ForeignKey(
        "users.User",
        verbose_name=_("Uploaded by"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="uploadedcollectionruns_of_user",
        related_query_name="uploadedcollectionrun_of_user",
    )
    total_amount = DecimalField(_("Total"), default=Decimal(0), **MONEY)
    count = PositiveIntegerField(_("Number of debits"), default=0)

    class Meta:
        verbose_name = _("Collection run")
        verbose_name_plural = _("Collection runs")
        ordering = ["-collection_date", "-created"]

    def __str__(self):
        return f"{self.collection_date:%Y-%m-%d} ({self.count})"


class Collection(TimeStampedModel):
    class Kind(TextChoices):
        FEE = "fee", _("Fee")
        DEPOSIT = "deposit", _("Deposit")
        DEPOSIT_REFUND = "deposit_refund", _("Deposit refund")

    class Status(IntegerChoices):
        PLANNED = 1, _("Planned")
        NOTIFIED = 2, _("Notified")
        SUBMITTED = 3, _("Submitted")
        COLLECTED = 4, _("Collected")
        RETURNED = 5, _("Returned")
        INVOICED = 6, _("Invoiced")
        PAID = 7, _("Paid")
        CANCELLED = 8, _("Cancelled")

    FINAL_STATUSES = (Status.PAID, Status.CANCELLED)

    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    history = AuditlogHistoryField()
    agreement = ForeignKey(
        Agreement,
        verbose_name=pgettext_lazy("agreements", "Agreement"),
        on_delete=PROTECT,
        related_name="collections_of_agreement",
        related_query_name="collection_of_agreement",
    )
    kind = CharField(_("Kind"), max_length=20, choices=Kind.choices, default=Kind.FEE)
    period_start = DateField(_("Period start"))
    period_end = DateField(_("Period end"))
    due_date = DateField(_("Due date"))
    amount = DecimalField(_("Amount"), **MONEY)
    mandate = ForeignKey(
        SepaMandate,
        verbose_name=_("Mandate"),
        on_delete=PROTECT,
        null=True,
        blank=True,
        related_name="collections_of_mandate",
        related_query_name="collection_of_mandate",
    )
    status = IntegerField(_("Status"), choices=Status.choices, default=Status.PLANNED)
    reference = CharField(
        _("Collection reference"), max_length=35, unique=True, null=True, blank=True
    )
    run = ForeignKey(
        CollectionRun,
        verbose_name=_("Run"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="collections_of_run",
        related_query_name="collection_of_run",
    )
    notified_at = DateTimeField(_("Notified at"), null=True, blank=True)
    collected_at = DateField(_("Collected on"), null=True, blank=True)
    returned_at = DateTimeField(_("Returned at"), null=True, blank=True)
    return_text = TextField(_("Return text"), blank=True)
    invoice_number = CharField(_("Invoice number"), max_length=64, blank=True)
    invoiced_at = DateTimeField(_("Invoiced at"), null=True, blank=True)
    invoice_amount = DecimalField(_("Invoice amount"), null=True, blank=True, **MONEY)
    paid_at = DateTimeField(_("Paid at"), null=True, blank=True)
    status_note = TextField(_("Note"), blank=True)

    class Meta:
        verbose_name = _("Collection")
        verbose_name_plural = _("Collections")
        ordering = ["due_date", "id"]
        constraints = [
            UniqueConstraint(
                fields=["agreement", "kind", "period_start"],
                name="collection_unique_period_per_agreement_and_kind",
            ),
        ]

    def __str__(self):
        return f"{self.reference or self.pk} {self.amount} €"

    @property
    def is_final(self):
        return self.status in self.FINAL_STATUSES


class SyncState(TimeStampedModel):
    """Remembers when a nightly synchronisation last succeeded."""

    key = CharField(_("Key"), max_length=64, unique=True)
    synced_at = DateTimeField(_("Last successful sync"))

    class Meta:
        verbose_name = _("Sync state")
        verbose_name_plural = _("Sync states")

    def __str__(self):
        return f"{self.key}: {self.synced_at:%Y-%m-%d %H:%M}"


class UnmatchedReturn(TimeStampedModel):
    """A negative bank transaction that matched no collection."""

    transaction_id = CharField(_("Transaction"), max_length=64, unique=True)
    booked_on = DateField(_("Booked on"), null=True, blank=True)
    amount = DecimalField(_("Amount"), **MONEY)
    text = TextField(_("Text"), blank=True)
    resolved = BooleanField(_("Resolved"), default=False)

    class Meta:
        verbose_name = _("Unmatched return")
        verbose_name_plural = _("Unmatched returns")
        ordering = ["-booked_on", "-id"]

    def __str__(self):
        return f"{self.booked_on} {self.amount} €"


auditlog.register(AgreementKind, exclude_fields=["updated"])
auditlog.register(Agreement, exclude_fields=["updated"])
auditlog.register(SepaMandate, exclude_fields=["updated", "iban"])
auditlog.register(Collection, exclude_fields=["updated"])
auditlog.register(CollectionRun, exclude_fields=["updated"])
