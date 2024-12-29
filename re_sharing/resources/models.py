import uuid
from datetime import timedelta

from django.core.validators import FileExtensionValidator
from django.db.models import CASCADE
from django.db.models import PROTECT
from django.db.models import SET_NULL
from django.db.models import CharField
from django.db.models import DateTimeField
from django.db.models import ForeignKey
from django.db.models import ImageField
from django.db.models import IntegerField
from django.db.models import ManyToManyField
from django.db.models import Model
from django.db.models import PositiveIntegerField
from django.db.models import TextField
from django.db.models import UUIDField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from tinymce.models import HTMLField

from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import TimeStampedModel


class Access(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = CharField(_("Name"), max_length=255)
    slug = AutoSlugField(_("Slug"), populate_from="name")
    instructions = TextField(_("Instructions"), max_length=512)

    class Meta:
        verbose_name = _("Access")
        verbose_name_plural = _("Accesses")
        ordering = ["name"]

    def __str__(self):
        return self.name


class AccessCode(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    access = ForeignKey(
        Access,
        verbose_name=_("Access"),
        on_delete=CASCADE,
        related_name="accesscodes_of_access",
        related_query_name="accesscode_of_access",
    )
    code = CharField(_("Code"), max_length=256)
    validity_start = DateTimeField(_("Validity start"))
    organization = ForeignKey(
        "organizations.Organization",
        verbose_name=_("Organization"),
        on_delete=CASCADE,
        related_name="organizations_of_access",
        related_query_name="organization_of_access",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Access code")
        verbose_name_plural = _("Access codes")
        ordering = ["validity_start"]

    def __str__(self):
        return self.access.name + " " + self.validity_start.strftime("%Y-%m-%d %H:%M")


class Resource(Model):
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    name = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    access = ForeignKey(
        Access,
        verbose_name=_("Access"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="rooms_of_access",
        related_query_name="room_of_access",
    )
    description = HTMLField(_("Description"), max_length=5000, blank=True)
    accessibility = HTMLField(_("Accessibility"), max_length=5000, blank=True)
    square_meters = PositiveIntegerField(_("Square Meters"), null=True, blank=True)
    max_persons = PositiveIntegerField(_("Maximum Number of Persons"), default=5)
    bookable_times = CharField(_("General Bookable Times"), max_length=128, blank=True)
    pricing = TextField(_("Pricing conditions"), max_length=512, blank=True)
    included_equipment = TextField(_("Included Equipment"), max_length=512, blank=True)
    manager = ForeignKey("users.User", on_delete=PROTECT, verbose_name=_("Manager"))
    address = CharField(_("Address"), max_length=256)

    class Meta:
        verbose_name = _("Resource")
        verbose_name_plural = _("Rooms")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("rooms:show-room", kwargs={"room_slug": self.slug})

    def is_booked(self, timespan):
        return self.bookings_of_room.filter(timespan__overlap=timespan).exists()

    def is_bookable(self, start_datetime):
        end_datetime = start_datetime + timedelta(minutes=30)
        return not self.bookings_of_room.filter(
            timespan__overlap=(start_datetime, end_datetime),
            status=BookingStatus.CONFIRMED,
        ).exists()


def create_roomimage_path(instance, filename):
    room_slug = instance.room.slug

    return f"rooms/{room_slug}-{filename}"


class ResourceImage(TimeStampedModel):
    room = ForeignKey(
        Resource,
        verbose_name=_("Resource"),
        on_delete=CASCADE,
        related_name="roomimages_of_room",
        related_query_name="roomimage_of_room",
    )
    image = ImageField(
        upload_to="room_images/",
        validators=[FileExtensionValidator(allowed_extensions=["png", "jpg", "jpeg"])],
    )
    description = CharField(
        verbose_name=_("Description"),
        max_length=250,
        blank=True,
    )

    class Meta:
        verbose_name = _("Resource Image")
        verbose_name_plural = _("Resource Images")

    def __str__(self):
        return self.room.name + ": " + self.description

    def get_absolute_url(self):
        return reverse("rooms:show-room", kwargs={"slug": self.room.slug})


class Compensation(TimeStampedModel):
    room = ManyToManyField(
        Resource,
        verbose_name=_("Resource"),
        related_name="compensations_of_room",
        related_query_name="compensation_of_room",
    )
    name = CharField(_("Name"), max_length=255)
    conditions = CharField(_("Conditions"), max_length=512, blank=True)
    hourly_rate = IntegerField(_("Hourly Rate"), null=True, blank=True)

    class Meta:
        verbose_name = _("Compensation")
        verbose_name_plural = _("Compensations")

    def __str__(self):
        if self.hourly_rate is None:
            return self.name
        return self.name + " (" + str(self.hourly_rate) + " €)"
