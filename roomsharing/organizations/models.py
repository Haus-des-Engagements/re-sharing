from django.db.models import CharField
from django.db.models import Model
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField


class Organization(Model):
    name = CharField(_("Name"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    street = CharField(_("Street"), max_length=56)
    house_number = CharField(_("House Number"), max_length=8)
    zip_code = CharField(_("Zip Code"), max_length=12)
    city = CharField(_("City"), max_length=24)

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ["name"]

    def __str__(self):
        return self.name
