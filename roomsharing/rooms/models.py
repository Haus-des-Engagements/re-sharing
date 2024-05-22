from pathlib import Path

from django.core.validators import FileExtensionValidator
from django.db.models import CASCADE
from django.db.models import CharField
from django.db.models import ForeignKey
from django.db.models import ImageField
from django.db.models import Model
from django.db.models import PositiveIntegerField
from django.db.models import TextField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from PIL import Image

from roomsharing.utils.models import TimeStampedModel


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


def create_roomimage_path(instance, filename):
    room_slug = instance.room.slug

    return f"rooms/{room_slug}/room_images/{filename}"


class RoomImage(TimeStampedModel):
    room = ForeignKey(
        Room,
        verbose_name=_("Room"),
        on_delete=CASCADE,
        related_name="roomimages_of_room",
        related_query_name="roomimage_of_room",
    )
    image = ImageField(
        upload_to=create_roomimage_path,
        validators=[FileExtensionValidator(allowed_extensions=["png", "jpg", "jpeg"])],
    )
    description = CharField(
        verbose_name=_("Description"),
        max_length=250,
        blank=True,
    )

    class Meta:
        verbose_name = _("Room Image")
        verbose_name_plural = _("Room Images")

    def image_name(self):
        return Path(self.image.name).name

    def get_absolute_url(self):
        return reverse("rooms:detail", kwargs={"slug": self.room.slug})

    def save(self, *args, **kwargs):
        #  shrink image to max-width/height of 1920px, change quality and optimize
        super().save(*args, **kwargs)
        img = Image.open(self.image.path)
        img.thumbnail([1920, 1920])
        img.save(self.image.path, quality=90, optimize=True)
