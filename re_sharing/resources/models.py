import uuid
from datetime import timedelta

from django.core.files.storage import storages
from django.core.validators import FileExtensionValidator
from django.db.models import CASCADE
from django.db.models import SET_NULL
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import DateField
from django.db.models import DateTimeField
from django.db.models import ForeignKey
from django.db.models import ImageField
from django.db.models import IntegerField
from django.db.models import ManyToManyField
from django.db.models import Model
from django.db.models import PositiveIntegerField
from django.db.models import Q
from django.db.models import TextChoices
from django.db.models import TextField
from django.db.models import TimeField
from django.db.models import UUIDField
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from tinymce.models import HTMLField

from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import TimeStampedModel


class Location(TimeStampedModel):
    name = CharField(_("Name"), max_length=255)
    address = CharField(_("Address"), max_length=256)
    slug = AutoSlugField(_("Slug"), populate_from="name", editable=True)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.address})"


class Access(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = CharField(_("Name"), max_length=255)
    slug = AutoSlugField(_("Slug"), populate_from="name", editable=True)
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
    class ResourceTypeChoices(TextChoices):
        ROOM = "room", _("Room")
        PARKING_LOT = "parking_lot", _("Parking lot")

    uuid = UUIDField(default=uuid.uuid4, editable=False)
    name = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from="name")
    access = ForeignKey(
        Access,
        verbose_name=_("Access"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="resources_of_access",
        related_query_name="resource_of_access",
    )
    description = HTMLField(_("Description"), max_length=5000, blank=True)
    accessibility = HTMLField(_("Accessibility"), max_length=5000, blank=True)
    square_meters = PositiveIntegerField(_("Square Meters"), null=True, blank=True)
    max_persons = PositiveIntegerField(_("Maximum Number of Persons"), default=5)
    bookable_times = CharField(_("General Bookable Times"), max_length=128, blank=True)
    included_equipment = TextField(_("Included Equipment"), max_length=512, blank=True)
    location = ForeignKey(
        Location,
        verbose_name=_("Location"),
        on_delete=SET_NULL,
        null=True,
        blank=True,
        related_name="resources_of_location",
        related_query_name="resource_of_location",
    )
    is_private = BooleanField(
        _("Private"),
        help_text=_("Only bookable with specific permissions"),
        default=False,
    )
    type = CharField(max_length=50, choices=ResourceTypeChoices)

    class Meta:
        verbose_name = _("Resource")
        verbose_name_plural = _("Resources")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("resources:show-resource", kwargs={"resource_slug": self.slug})

    def is_booked(self, timespan):
        return self.bookings_of_resource.filter(
            timespan__overlap=timespan, status=BookingStatus.CONFIRMED
        ).exists()

    def is_bookable(self, start_datetime):
        end_datetime = start_datetime + timedelta(minutes=30)
        return not self.bookings_of_resource.filter(
            timespan__overlap=(start_datetime, end_datetime),
            status=BookingStatus.CONFIRMED,
        ).exists()

    def is_bookable_by_organization(self, organization):
        if not self.is_private:
            return True
        # if the organization is in an OrganizationGroup that has the permission to
        # book the private ressource
        if self.bookableprivateressources_of_organizationgroup.filter(
            organization_of_organizationgroups=organization
        ).exists():
            return True
        # if the organization is in an OrganizationGroup that has auto-confirmation for
        # the resource
        if self.autoconfirmedresources_of_organizationgroup.filter(
            organization_of_organizationgroups=organization
        ).exists():
            return True
        return False

    def get_bookable_compensations(self, organization):
        return Compensation.objects.filter(resource=self).filter(
            Q(organization_groups=None)
            | Q(organization_groups__organization_of_organizationgroups=organization)
        )


def create_resourceimage_path(instance, filename):
    resource_slug = instance.resource.slug

    return f"resource_images/{resource_slug}-{filename}"


def select_default_storage():
    return storages["default"]


class ResourceImage(TimeStampedModel):
    resource = ForeignKey(
        Resource,
        verbose_name=_("Resource"),
        on_delete=CASCADE,
        related_name="resourceimages_of_resource",
        related_query_name="resourceimage_of_resource",
    )
    image = ImageField(
        upload_to="resource_images/",
        validators=[FileExtensionValidator(allowed_extensions=["png", "jpg", "jpeg"])],
        storage=select_default_storage,
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
        return self.resource.name + ": " + self.description

    def get_absolute_url(self):
        return reverse(
            "resources:show-resource", kwargs={"resource_slug": self.resource.slug}
        )


class ResourceRestriction(TimeStampedModel):
    resources = ManyToManyField(
        Resource,
        verbose_name=_("Resources"),
        related_name="restrictions_of_resource",
        related_query_name="restriction_of_resource",
        help_text=_("Select the resources this restriction applies to."),
    )
    exempt_organization_groups = ManyToManyField(
        "organizations.OrganizationGroup",
        verbose_name=_("Exempt organization groups"),
        related_name="exempt_restrictions_of_organizationgroup",
        related_query_name="exempt_restriction_of_organizationgroup",
        blank=True,
        help_text=_("Organizations in these groups are exempt from this restriction."),
    )
    start_time = TimeField(
        _("Start time"), help_text=_("Start time of the restriction.")
    )
    end_time = TimeField(_("End time"), help_text=_("End time of the restriction."))
    days_of_week = CharField(
        _("Days of week"),
        max_length=13,
        help_text=_("Comma-separated list of weekday numbers (0=Monday, 6=Sunday)."),
    )
    start_date = DateField(
        _("Start date"),
        null=True,
        blank=True,
        help_text=_(
            "Start date of the restriction. Leave empty to apply from the beginning."
        ),
    )
    end_date = DateField(
        _("End date"),
        null=True,
        blank=True,
        help_text=_("End date of the restriction. Leave empty to apply indefinitely."),
    )
    message = CharField(
        _("Message"),
        max_length=512,
        help_text=_("Message to display when the restriction applies."),
    )
    is_active = BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Resource restriction")
        verbose_name_plural = _("Resource restrictions")
        ordering = ["id"]

    def __str__(self):
        return f"Restriction: {self.message}"

    def applies_to_organization(self, organization):
        """
        Check if this restriction applies to the given organization.
        """
        # If the organization is in an exempt group, the restriction doesn't apply
        if self.exempt_organization_groups.filter(
            organization_of_organizationgroups=organization
        ).exists():
            return False
        return True

    def applies_to_datetime(self, dt):
        """
        Check if this restriction applies to the given datetime.
        """
        # Check if the date is within the date range
        date = dt.date()
        if self.start_date and date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False

        # Check if the day of week is in the restriction's days of week
        weekday = dt.weekday()
        days = [int(d.strip()) for d in self.days_of_week.split(",")]
        if weekday not in days:
            return False

        # Check if the time is between start_time and end_time
        time = dt.time()
        if not (self.start_time <= time < self.end_time):
            return False

        return True


class Compensation(TimeStampedModel):
    resource = ManyToManyField(
        Resource,
        verbose_name=_("Resource"),
        related_name="compensations_of_resource",
        related_query_name="compensation_of_resource",
        blank=True,
        help_text=_(
            "If no resource is selected, the compensation is bookable "
            "for all resources."
        ),
    )
    name = CharField(_("Name"), max_length=255)
    slug = AutoSlugField(
        _("Slug"), populate_from=("name", "hourly_rate"), editable=True
    )
    conditions = CharField(_("Conditions"), max_length=512, blank=True)
    hourly_rate = IntegerField(_("Hourly Rate"), null=True, blank=True)
    is_active = BooleanField(_("Active"), default=True)
    organization_groups = ManyToManyField(
        "organizations.OrganizationGroup",
        verbose_name=_("Organization group"),
        related_name="compensations_of_organizationgroup",
        related_query_name="compensation_of_organizationgroup",
        blank=True,
        help_text=_(
            "If no group is selected, the compensation is bookable "
            "for all organizations."
        ),
    )

    class Meta:
        verbose_name = _("Compensation")
        verbose_name_plural = _("Compensations")
        ordering = [Lower("name")]

    def __str__(self):
        if self.hourly_rate is None:
            return self.name
        return self.name + " (" + str(self.hourly_rate) + " €)"

    def is_bookable_by_organization(self, organization):
        # if no OrganizationGroup is specified for the Compensation, anyone can book it
        if not self.organization_groups.exists():
            return True
        # if an OrganizationGroups are specified for the Compensation, the organization
        # has to be in one of these OrganizationGroups
        if self.organization_groups.filter(
            organization_of_organizationgroups=organization
        ).exists():
            return True
        return False
