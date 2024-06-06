from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import Model
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField


class Organization(Model):
    class Type(IntegerChoices):
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

    name = CharField(_("Name"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    street = CharField(_("Street"), max_length=56)
    house_number = CharField(_("House number"), max_length=8, blank=True)
    zip_code = CharField(_("Zip Code"), max_length=12)
    city = CharField(_("City"), max_length=24)
    type = IntegerField(verbose_name=_("Status"), choices=Type.choices)
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
