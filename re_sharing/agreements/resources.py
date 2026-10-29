"""Spreadsheet import of existing agreements and paper mandates in the admin.

Files are not imported: signed contracts and mandates are uploaded on the
agreement and mandate pages afterwards. Rows are validated like the admin
form, including the unique constraints. The admin shows a preview first and
offers the import only when no row has an error.
"""

from import_export import fields
from import_export import resources
from import_export.widgets import ForeignKeyWidget

from re_sharing.organizations.models import Organization

from .models import Agreement
from .models import AgreementKind
from .models import SepaMandate


class AgreementResource(resources.ModelResource):
    organization = fields.Field(
        column_name="organization",
        attribute="organization",
        widget=ForeignKeyWidget(Organization, "id"),
    )
    organization_name = fields.Field(
        column_name="organization_name",
        attribute="organization__name",
        readonly=True,
    )
    kind = fields.Field(
        column_name="kind",
        attribute="kind",
        widget=ForeignKeyWidget(AgreementKind, "slug"),
    )

    class Meta:
        model = Agreement
        fields = (
            "id",
            "organization",
            "organization_name",
            "kind",
            "status",
            "amount",
            "deposit_amount",
            "start_date",
            "end_date",
            "decided_at",
            "signed_on",
            "contact_person_function",
            "details",
            "notes",
        )
        clean_model_instances = True
        use_transactions = True
        skip_unchanged = True
        report_skipped = True


class SepaMandateResource(resources.ModelResource):
    """Import only: an export would put full IBANs into a file."""

    agreement = fields.Field(
        column_name="agreement",
        attribute="agreement",
        widget=ForeignKeyWidget(Agreement, "id"),
    )

    class Meta:
        model = SepaMandate
        fields = (
            "id",
            "agreement",
            "reference",
            "account_holder",
            "iban",
            "bic",
            "bank_name",
            "signed_on",
            "revoked_on",
        )
        clean_model_instances = True
        use_transactions = True
        skip_unchanged = True
        report_skipped = True
