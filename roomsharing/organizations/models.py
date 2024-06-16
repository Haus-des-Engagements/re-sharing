from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.db.models import CASCADE
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.utils.models import TimeStampedModel


class Organization(TimeStampedModel):
    class LegalForm(IntegerChoices):
        NO_LEGAL_FORM = 1, _("Without legal form")
        REGISTERED_ASSOCIATION = 2, _("Registered association")
        NOT_REGISTERED_ASSOCIATION = 3, _("Not registered association")
        FOUNDATION = 4, _("Foundation")
        CIVIL_LAW_COMPANY = 5, _("Civil law company")
        LIMITED_COMPANY = 6, _("Limited company")
        LIMITED_CHARITABLE_COMPANY = 7, _("Limited charitable company")
        COOPERATIVE = 8, _("Cooperative")
        CHARITABLE_COOPERATIVE = 9, _("Charitable cooperative")
        INDIVIDUAL_ENTREPRENEUR = 10, _("Individual entrepreneur")
        OTHER = 11, _("Other")

    history = AuditlogHistoryField()
    name = CharField(_("Name"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    street = CharField(_("Street"), max_length=56)
    house_number = CharField(_("House number"), max_length=8, blank=True)
    zip_code = CharField(_("Zip Code"), max_length=12)
    city = CharField(_("City"), max_length=24)
    legal_form = IntegerField(verbose_name=_("Legal form"), choices=LegalForm.choices)
    certificate_of_tax_exemption = BooleanField(
        _("Certificate of tax exemption"), default=False
    )

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("organizations:organization_detail", args=[str(self.slug)])


class Membership(TimeStampedModel):
    class Role(IntegerChoices):
        ADMIN = 1, _("Administrator")
        BOOKER = 2, _("Booker")

    class Status(IntegerChoices):
        PENDING = 1, _("Pending")
        CONFIRMED = 2, _("Confirmed")
        REJECTED = 3, _("Rejected")

    history = AuditlogHistoryField()
    user = ForeignKey(
        "users.User",
        verbose_name=_("User"),
        related_name="users_of_membership",
        related_query_name="user_of_membership",
        blank=True,
        on_delete=CASCADE,
    )
    organization = ForeignKey(
        Organization,
        verbose_name=_("Organization"),
        related_name="organizations_of_membership",
        related_query_name="organization_of_membership",
        blank=True,
        on_delete=CASCADE,
    )
    role = IntegerField(
        verbose_name=_("Role"), choices=Role.choices, default=Role.BOOKER
    )
    status = IntegerField(
        verbose_name=_("Status"), choices=Status.choices, default=Status.PENDING
    )

    class Meta:
        unique_together = ("user", "organization")
        verbose_name = _("Membership")
        verbose_name_plural = _("Memberships")
        ordering = ["id"]

    def __str__(self):
        return self.user.__str__() + " - " + self.organization.name


auditlog.register(Organization, exclude_fields=["created, updated"])
auditlog.register(Membership, exclude_fields=["created, updated"])
