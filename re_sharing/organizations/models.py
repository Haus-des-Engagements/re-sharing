import uuid
from pathlib import Path

import magic
from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.core.exceptions import ValidationError
from django.core.files.storage import storages
from django.db.models import CASCADE
from django.db.models import PROTECT
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import DateField
from django.db.models import EmailField
from django.db.models import FileField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import ManyToManyField
from django.db.models import TextChoices
from django.db.models import TextField
from django.db.models import UUIDField
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from re_sharing.resources.models import Resource
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import TimeStampedModel


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


class OrganizationGroup(TimeStampedModel):
    name = CharField(_("Name"), max_length=160)
    description = CharField(_("Description"), max_length=2048)
    slug = AutoSlugField(populate_from="name", unique=True, editable=True)
    auto_confirmed_resources = ManyToManyField(
        Resource,
        verbose_name=_("Auto confirmed resources"),
        related_name="autoconfirmedresources_of_organizationgroup",
        related_query_name="autoconfirmedresource_of_organizationgroup",
        blank=True,
    )
    show_on_organization_creation = BooleanField(
        _("Show on organization creation"), default=False
    )
    show_on_organization_creation_wording = CharField(
        _("This will be displayed in the form"), max_length=256, blank=True
    )
    bookable_private_resources = ManyToManyField(
        Resource,
        verbose_name=_("Bookable private resources"),
        related_name="bookableprivateressources_of_organizationgroup",
        related_query_name="bookableprivateressource_of_organizationgroup",
        blank=True,
    )
    default_group = BooleanField(_("Group activated by default"), default=False)

    class Meta:
        verbose_name = _("Organization group")
        verbose_name_plural = _("Organization groups")
        ordering = ["id"]

    def __str__(self):
        return self.name


def custom_usage_agreement_upload_to(instance, filename):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    organization_slug = instance.slug  # Ensure `slug` is populated before saving
    extension = Path(filename).suffix  # Get the file extension
    new_filename = f"{timestamp}_{organization_slug}_usage_agreement{extension}"
    return str(Path("usage_agreements") / new_filename)


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
    public_name = CharField(
        _("Public name"),
        max_length=160,
        blank=True,
        help_text=_(
            "This is the name that appears on the public timetables. "
            "Only relevant if you wish to hide your official name publicly."
        ),
    )
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
    send_booking_emails_only_to_organization = BooleanField(
        _("All mails will be send to the organization and not to the user."),
        default=False,
    )
    monthly_bulk_access_codes = BooleanField(
        _("All access codes for the next month will be sent in one mail on the 20th."),
        default=False,
    )
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
    is_public = BooleanField(
        _("Organization information is publicly visible"),
        default=True,
        help_text=_(
            "If checked, we'll show the following information to others: name, "
            "description, city, website, area of activity"
        ),
    )
    values_approval = BooleanField(_("Approval of values"))
    notes = CharField(
        _("Notes"), max_length=512, blank=True, help_text=_("Internal notes")
    )
    usage_agreement = FileField(
        _("Usage agreement"),
        upload_to=custom_usage_agreement_upload_to,
        validators=[validate_is_pdf],
        blank=True,
        null=True,
        storage=select_private_storage,
    )
    usage_agreement_date = DateField(
        _("Date of the signed usage agreement"), blank=True, null=True
    )
    organization_groups = ManyToManyField(
        OrganizationGroup,
        verbose_name=_("Organization group"),
        related_name="organizations_of_organizationgroups",
        related_query_name="organization_of_organizationgroups",
        blank=True,
    )

    class Meta:
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")
        ordering = [Lower("name")]

    def __str__(self):
        return self.name

    def is_cancelable(self):
        return self.status != BookingStatus.CANCELLED

    def is_confirmable(self):
        return self.status == BookingStatus.PENDING

    def get_absolute_url(self):
        return reverse("organizations:show-organization", args=[str(self.slug)])

    def get_confirmed_admins(self):
        """
        Fetch all users who are confirmed admins of this organization.
        """
        from re_sharing.users.models import User

        return User.objects.filter(
            user_of_bookingpermission__organization=self,
            user_of_bookingpermission__role=BookingPermission.Role.ADMIN,
            user_of_bookingpermission__status=BookingPermission.Status.CONFIRMED,
        )

    def get_confirmed_users(self):
        """
        Fetch all users who are confirmed users of this organization.
        """
        from re_sharing.users.models import User

        return User.objects.filter(
            user_of_bookingpermission__organization=self,
            user_of_bookingpermission__status=BookingPermission.Status.CONFIRMED,
        )

    def has_confirmed_user(self, user):
        """
        Check if a user is confirmed for an organization
        """

        return BookingPermission.objects.filter(
            organization=self, user=user, status=BookingPermission.Status.CONFIRMED
        ).exists()


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
        BOOKING_SERIES_CONFIRMATION = (
            "booking_series_confirmation",
            _("Booking series confirmation"),
        )
        BOOKING_SERIES_CANCELLATION = (
            "booking_series_cancellation",
            _("Booking series cancellation"),
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
        MANAGER_NEW_BOOKING_SERIES = (
            "manager_new_booking_series",
            _("Manager new booking series"),
        )
        MANAGER_NEW_BOOKING = "manager_new_booking", _("Manager new booking")
        MANAGER_NEW_ORGANIZATION_MESSAGE = (
            "manager_new_organization_message",
            _("Manager new organization message"),
        )
        NEW_BOOKING_MESSAGE = "new_booking_message", _("New booking message")
        NEW_ORGANIZATION_MESSAGE = (
            "new_organization_message",
            _("New organization message"),
        )

    email_type = CharField(max_length=50, choices=EmailTypeChoices, unique=True)
    subject = CharField(max_length=255)
    body = TextField()
    active = BooleanField(_("Send this email out."), default=False)

    class Meta:
        verbose_name = _("E-Mail template")
        verbose_name_plural = _("E-Mail template")
        ordering = ["email_type"]

    def __str__(self):
        return self.get_email_type_display()


class OrganizationMessage(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    organization = ForeignKey(
        Organization,
        verbose_name=_("Organization"),
        on_delete=CASCADE,
        related_name="organizationmessages_of_organization",
        related_query_name="organizationmessage_of_organization",
    )
    text = CharField(_("Message"), max_length=800)
    user = ForeignKey(
        "users.User",
        verbose_name=_("User"),
        on_delete=PROTECT,
        related_name="organizationmessages_of_user",
        related_query_name="organizationmessage_of_user",
    )

    class Meta:
        verbose_name = _("Organization Message")
        verbose_name_plural = _("Organization Messages")
        ordering = ["created"]

    def get_absolute_url(self):
        return reverse(
            "organizations:show-organization-messages",
            args=[str(self.organization.slug)],
        )


auditlog.register(Organization, exclude_fields=["updated"])
auditlog.register(BookingPermission, exclude_fields=["updated"])
auditlog.register(OrganizationMessage, exclude_fields=["created, updated"])
