import uuid

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.db.models import CASCADE
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import UUIDField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.rooms.models import Room
from roomsharing.utils.models import BookingStatus
from roomsharing.utils.models import TimeStampedModel


class Organization(TimeStampedModel):
    class Status(IntegerChoices):
        PENDING = 1, _("Pending")
        CONFIRMED = 2, _("Confirmed")
        REJECTED = 3, _("Rejected")

    class ActivityArea(IntegerChoices):
        SPORT_EXERCISE = 1, _("Sport and exercise")
        CULTURE_MUSIC = 2, _("Culture and music")
        SOCIAL = 3, _("Social area")
        SCHOOL_NURSERY = 4, _("School or nursery area")
        CHURCH_RELIGIOUS = 5, _("Church or religious area")
        LEISURE_SOCIAL_INTERACTION = 6, _("Leisure and social interaction")
        ENVIRONMENT_NATURE_ANIMALS = (
            7,
            _("Environment, nature protection or animal rights"),
        )
        YOUTH_ADULT_EDUCATION = 8, _("Youth work outside school or adult education")
        POLITICS = 9, _("Politics and political interest groups")
        AMBULANCE_FIREBRIGADE = (
            10,
            _("Accident or ambulance service or voluntary fire brigade"),
        )
        HEALTH = 11, _("Health area")
        PROF_INTEREST = 12, _("Professional interest groups outside work")
        JUSTICE_CRIMINALITY = 13, _("Justice and criminality")
        NOT_MENTIONED = 14, _("Area not yet mentioned")

    class LegalForm(IntegerChoices):
        NO_LEGAL_FORM = 1, _("Without legal form")
        REGISTERED_ASSOCIATION = 2, _("Registered association")
        NOT_REGISTERED_ASSOCIATION = 3, _("Not registered association")
        FOUNDATION = 4, _("Foundation")
        CIVIL_LAW_COMPANY = 5, _("Civil law company")
        LIMITED_COMPANY = 6, _("Limited company")
        COOPERATIVE = 7, _("Cooperative")
        INDIVIDUAL_ENTREPRENEUR = 8, _("Individual entrepreneur")
        OTHER = 9, _("Other")

    uuid = UUIDField(default=uuid.uuid4, editable=False)
    history = AuditlogHistoryField()
    name = CharField(_("Name"), max_length=160)
    description = CharField(
        _("Description"),
        max_length=512,
        help_text=_("Describe shortly what your organization does."),
    )
    slug = AutoSlugField(populate_from="name", unique=True, editable=False)
    street_and_housenb = CharField(_("Street and housenumber"), max_length=56)
    zip_code = CharField(_("Zip Code"), max_length=12)
    city = CharField(_("City"), max_length=24)
    email = EmailField(_("E-Mail"), max_length=64)
    phone = CharField(_("Phone number"), max_length=32)
    website = CharField(_("Website"), max_length=128, blank=True)
    legal_form = IntegerField(verbose_name=_("Legal form"), choices=LegalForm.choices)
    other_legal_form = CharField(_("Other legal form"), max_length=160, blank=True)
    is_charitable = BooleanField(
        _("We are a charitable organization."),
        help_text=_(
            "Only applicable if you have a valid certificate of tax exemption."
        ),
        default=False,
    )
    status = IntegerField(
        verbose_name=_("Status"), choices=Status.choices, default=Status.PENDING
    )
    area_of_activity = IntegerField(
        verbose_name=_("Main area of activity"), choices=ActivityArea.choices
    )
    is_coworking = BooleanField(
        _("Co-Worker:in"),
        help_text=_("Only applicable if you are currently co-working in the HdE"),
        default=False,
    )
    is_public = BooleanField(
        _("Organization information is publicly visible"),
        default=True,
        help_text=_(
            "If checked, we'll show the following information to others: name, "
            "description, city, website, area of activity"
        ),
    )
    values_approval = BooleanField(_("Approval of values"))
    entitled = BooleanField(_("Approval of entitlement"))
    notes = CharField(
        _("Notes"), max_length=512, blank=True, help_text=_("Internal notes")
    )

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("organizations:show-organization", args=[str(self.slug)])

    def default_booking_status(self, room):
        default_booking_status = self.defaultbookingstatuses_of_organization.filter(
            room=room
        )
        if default_booking_status:
            return default_booking_status.first().status
        return BookingStatus.PENDING


class BookingPermission(TimeStampedModel):
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
        related_name="users_of_bookingpermission",
        related_query_name="user_of_bookingpermission",
        blank=True,
        on_delete=CASCADE,
    )
    organization = ForeignKey(
        Organization,
        verbose_name=_("Organization"),
        related_name="organizations_of_bookingpermission",
        related_query_name="organization_of_bookingpermission",
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
        verbose_name = _("Booking permission")
        verbose_name_plural = _("Booking permissions")
        ordering = ["id"]

    def __str__(self):
        return self.user.__str__() + " - " + self.organization.name


class DefaultBookingStatus(TimeStampedModel):
    history = AuditlogHistoryField()
    organization = ForeignKey(
        Organization,
        verbose_name=_("Organization"),
        related_name="defaultbookingstatuses_of_organization",
        related_query_name="defaultbookingstatus_of_organization",
        blank=True,
        on_delete=CASCADE,
    )
    room = ForeignKey(
        Room,
        verbose_name=_("Room"),
        on_delete=CASCADE,
        related_name="defaultbookingstatuses_of_room",
        related_query_name="defaultbookingstatus_of_room",
    )

    status = IntegerField(verbose_name=_("Status"), choices=BookingStatus.choices)

    class Meta:
        unique_together = ("room", "organization")
        verbose_name = _("Default booking status")
        verbose_name_plural = _("Default booking statuses")
        ordering = ["id"]

    def __str__(self):
        return (
            self.organization.name
            + " - "
            + self.room.name
            + ": "
            + self.get_status_display()
        )


auditlog.register(DefaultBookingStatus, exclude_fields=["created, updated"])
auditlog.register(Organization, exclude_fields=["created, updated"])
auditlog.register(BookingPermission, exclude_fields=["created, updated"])
