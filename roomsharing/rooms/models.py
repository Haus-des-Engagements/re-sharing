from django.db.models import CharField
from django.db.models import Model
from django.db.models import PositiveIntegerField
from django.db.models import TextField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField


class Room(Model):
    name = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    description = TextField(_("Description"), max_length=512)
    square_meters = PositiveIntegerField(_("Square Meters"), null=True, blank=True)
    max_persons = PositiveIntegerField(_("Maximum Number of Persons"), default=5)
    bookable_times = CharField(_("General Bookable Times"), max_length=128, blank=True)
    pricing = TextField(_("Pricing conditions"), max_length=512, blank=True)
    included_equipment = TextField(_("Included Equipment"), max_length=512, blank=True)
    bookable_equipment = TextField(_("Bookable Equipment"), max_length=512, blank=True)

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("rooms:detail", kwargs={"slug": self.slug})
