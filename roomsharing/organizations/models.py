import uuid
from pathlib import Path

import magic
from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.core.exceptions import ValidationError
from django.core.files.storage import storages
from django.db.models import CASCADE
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import EmailField
from django.db.models import FileField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import ManyToManyField
from django.db.models import TextChoices
from django.db.models import TextField
from django.db.models import UUIDField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.rooms.models import Room
from roomsharing.utils.models import BookingStatus
from roomsharing.utils.models import TimeStampedModel


def select_private_storage():
    return storages["private"]


def validate_is_pdf(file):
    valid_mime_types = ["application/pdf"]
    invalid_mime_type_message = "Unsupported file type."
    invalid_file_extension_message = "Unacceptable file extension."

    file_mime_type = magic.from_buffer(file.read(1024), mime=True)
    if file_mime_type not in valid_mime_types:
        raise ValidationError(invalid_mime_type_message)

    valid_file_extensions = [".pdf"]
    ext = Path(file.name).suffix
    if ext.lower() not in valid_file_extensions:
        raise ValidationError(invalid_file_extension_message)


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
        max_length=2048,
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
    usage_agreement = FileField(
        _("Usage agreement"),
        upload_to="usage_agreements/",
        validators=[validate_is_pdf],
        blank=True,
        null=True,
        storage=select_private_storage,
    )

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def is_cancelable(self):
        return self.status != BookingStatus.CANCELLED

    def is_confirmable(self):
        return self.status == BookingStatus.PENDING

    def get_absolute_url(self):
        return reverse("organizations:show-organization", args=[str(self.slug)])

    def default_booking_status(self, room):
        default_booking_status = self.defaultbookingstatuses_of_organization.filter(
            room=room
        )
        if default_booking_status:
            return default_booking_status.first().status
        return BookingStatus.PENDING

    def get_confirmed_admins(self):
        """
        Fetch all users who are confirmed admins of this organization.
        """
        from roomsharing.users.models import User

        return User.objects.filter(
            user_of_bookingpermission__organization=self,
            user_of_bookingpermission__role=BookingPermission.Role.ADMIN,
            user_of_bookingpermission__status=BookingPermission.Status.CONFIRMED,
        )


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
    room = ManyToManyField(
        Room,
        verbose_name=_("Rooms"),
        related_name="defaultbookingstatuses_of_room",
        related_query_name="defaultbookingstatus_of_room",
    )

    status = IntegerField(verbose_name=_("Status"), choices=BookingStatus.choices)

    class Meta:
        verbose_name = _("Default booking status")
        verbose_name_plural = _("Default booking statuses")
        ordering = ["id"]

    def __str__(self):
        return self.organization.name + ": " + self.get_status_display()


class EmailTemplate(TimeStampedModel):
    class EmailTypeChoices(TextChoices):
        BOOKING_CONFIRMATION = (
            "booking_confirmation",
            _("Booking confirmation"),
        )
        BOOKING_CANCELLATION = (
            "booking_cancellation",
            _("Booking cancellation"),
        )
        BOOKING_REMINDER = (
            "booking_reminder",
            _("Booking reminder"),
        )
        RECURRENCE_CONFIRMATION = (
            "recurrence_confirmation",
            _("Recurrence confirmation"),
        )
        RECURRENCE_CANCELLATION = (
            "recurrence_cancellation",
            _("Recurrence cancellation"),
        )
        ORGANIZATION_CONFIRMATION = (
            "organization_confirmation",
            _("Organization confirmation"),
        )
        ORGANIZATION_CANCELLATION = (
            "organization_cancellation",
            _("Organization cancellation"),
        )
        MANAGER_NEW_ORGANIZATION = (
            "manager_new_organization",
            _("Manager new organization"),
        )
        MANAGER_NEW_RECURRENCE = (
            "manager_new_recurrence",
            _("Manager new recurrence"),
        )
        MANAGER_NEW_BOOKING = "manager_new_booking", _("Manager new booking")

    email_type = CharField(max_length=50, choices=EmailTypeChoices, unique=True)
    subject = CharField(max_length=255)
    body = TextField()

    def __str__(self):
        return f"{self.get_email_type_display()} - {self.subject}"


auditlog.register(DefaultBookingStatus, exclude_fields=["updated"])
auditlog.register(Organization, exclude_fields=["updated"])
auditlog.register(BookingPermission, exclude_fields=["updated"])
auditlog.register(EmailTemplate, exclude_fields=["updated"])
