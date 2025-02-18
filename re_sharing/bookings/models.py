import uuid

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from dateutil.rrule import rrulestr
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields import RangeOperators
from django.contrib.postgres.indexes import GistIndex
from django.db.models import CASCADE
from django.db.models import PROTECT
from django.db.models import BooleanField
from django.db.models import CharField
from django.db.models import DateField
from django.db.models import DateTimeField
from django.db.models import DecimalField
from django.db.models import ForeignKey
from django.db.models import Index
from django.db.models import IntegerField
from django.db.models import PositiveIntegerField
from django.db.models import Q
from django.db.models import TextField
from django.db.models import TimeField
from django.db.models import UUIDField
from django.urls import reverse
from django.utils import formats
from django.utils import timezone
from django.utils.dates import WEEKDAYS
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from re_sharing.organizations.models import Organization
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.users.models import User
from re_sharing.utils.dicts import RRULE_DAILY_INTERVAL
from re_sharing.utils.dicts import RRULE_MONTHLY_INTERVAL
from re_sharing.utils.dicts import RRULE_WEEKLY_INTERVAL
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import TimeStampedModel


class BookingSeries(TimeStampedModel):
    history = AuditlogHistoryField()
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    title = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(
        populate_from=["get_human_readable_rule", "title"], editable=False
    )
    organization = ForeignKey(
        Organization,
        verbose_name=_("Organization"),
        on_delete=PROTECT,
        related_name="bookingseries_set_of_organization",
        related_query_name="bookingseries_of_organization",
    )
    user = ForeignKey(
        User,
        verbose_name=_("Initial Booking User"),
        on_delete=PROTECT,
        related_name="bookingseries_set_of_user",
        related_query_name="bookingseries_of_user",
    )
    resource = ForeignKey(
        Resource,
        verbose_name=_("Resource"),
        on_delete=PROTECT,
        related_name="bookingseries_set_of_resource",
        related_query_name="bookingseries_of_resource",
    )
    status = IntegerField(verbose_name=_("Status"), choices=BookingStatus.choices)
    rrule = TextField(_("Recurrence rule"))
    first_booking_date = DateField(_("Date of first booking"))
    last_booking_date = DateField(_("Date of last booking"), blank=True, null=True)
    # These fields are only stored for potential DST (Dailight Saving Time) problems.
    start_time = TimeField(_("Start Time"))
    end_time = TimeField(_("End Time"))
    compensation = ForeignKey(
        Compensation,
        verbose_name=_("Compensation"),
        on_delete=PROTECT,
        related_name="bookingseries_set_of_compensation",
        related_query_name="bookingseries_of_compensation",
    )
    total_amount_per_booking = DecimalField(
        _("Total amount per booking"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    invoice_address = CharField(_("Invoice address"), blank=True, max_length=256)
    activity_description = CharField(
        _("Activity description"),
        help_text=_("Please describe shortly what you are planning to do."),
        max_length=2048,
    )
    number_of_attendees = PositiveIntegerField(_("Number of attendees"), default=5)
    reminder_emails = BooleanField(_("Enable reminder e-mails"), default=True)
    import_id = CharField(
        _("Import ID"),
        help_text=_(
            "The ID of the record in the old system. This is used for referencing "
            "records even after migration."
        ),
        max_length=256,
        blank=True,
    )

    class Meta:
        verbose_name = _("Booking series")
        verbose_name_plural = _("Booking series")
        ordering = ["created"]

    def __str__(self):
        return str(self.title)

    def get_cancelled(self):
        return self.bookings_of_bookingseries.filter(status=BookingStatus.CANCELLED)

    def get_confirmed(self):
        return self.bookings_of_bookingseries.filter(status=BookingStatus.CONFIRMED)

    def get_pending(self):
        return self.bookings_of_bookingseries.filter(status=BookingStatus.PENDING)

    def get_absolute_url(self):
        return reverse(
            "bookings:show-booking-series", kwargs={"booking_series": self.slug}
        )

    def number_of_occurrences(self):
        return self.bookings_of_bookingseries.count()

    def get_first_booking(self):
        return self.bookings_of_bookingseries.first()

    def is_cancelable(self):
        return any(
            booking.is_cancelable() for booking in self.bookings_of_bookingseries.all()
        )

    def get_human_readable_frequency(self):
        rrule = rrulestr(self.rrule)
        if "DAILY" in self.rrule:
            return RRULE_DAILY_INTERVAL[rrule._interval - 1][1]  # noqa: SLF001

        if "WEEKLY" in self.rrule:
            return RRULE_WEEKLY_INTERVAL[rrule._interval - 1][1]  # noqa: SLF001

        return RRULE_MONTHLY_INTERVAL[rrule._interval - 1][1]  # noqa: SLF001

    def get_human_readable_end(self):
        rrule = rrulestr(self.rrule)
        if rrule._count:  # noqa: SLF001
            return _("ends after ") + str(rrule._count) + _(" times")  # noqa: SLF001

        if rrule._until:  # noqa: SLF001
            date_string = formats.date_format(rrule._until.date(), "SHORT_DATE_FORMAT")  # noqa: SLF001
            return _("ends at the ") + date_string

        return _("never ends")

    def get_human_readable_weekdays(self):
        rrule = rrulestr(self.rrule)
        if rrule._bynweekday:  # noqa: SLF001
            bynweekdays = [
                f"{day[1]}." + " " + WEEKDAYS[day[0]]
                if day[1] != -1
                else _("last ") + WEEKDAYS[day[0]]
                for day in rrule._bynweekday  # noqa: SLF001
            ]
            return _(" at the ") + ", ".join(bynweekdays)

        if rrule._byweekday:  # noqa: SLF001
            if len(rrule._byweekday) == 7:  # noqa: SLF001, PLR2004
                return _(" (on all days of the week)")

            weekdays = [str(WEEKDAYS[day]) + "s" for day in rrule._byweekday]  # noqa: SLF001
            return " (" + _("only ") + ", ".join(weekdays) + ")"

        return None

    def get_human_readable_monthdays(self):
        rrule = rrulestr(self.rrule)
        if rrule._bymonthday:  # noqa: SLF001
            monthdays = [str(day) + "." for day in rrule._bymonthday]  # noqa: SLF001
            return (
                " ("
                + _("only at the")
                + " "
                + ", ".join(monthdays)
                + " "
                + _("day")
                + ")"
            )
        return None

    def get_human_readable_rule(self):
        frequency = self.get_human_readable_frequency()
        ends = self.get_human_readable_end()
        weekdays = self.get_human_readable_weekdays()
        monthdays = self.get_human_readable_monthdays()
        if weekdays is not None:
            return frequency + weekdays + ", " + ends
        if monthdays is not None:
            return frequency + monthdays + ", " + ends
        return frequency + ", " + ends


class Booking(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    history = AuditlogHistoryField()
    title = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from=["start_date", "title"], editable=False)
    organization = ForeignKey(
        Organization,
        verbose_name=_("Booking Organization"),
        on_delete=PROTECT,
        related_name="bookings_of_organization",
        related_query_name="booking_of_organization",
    )
    user = ForeignKey(
        User,
        verbose_name=_("Initial Booking User"),
        on_delete=PROTECT,
        related_name="bookings_of_user",
        related_query_name="booking_of_user",
    )
    timespan = DateTimeRangeField("Date Time Range", default_bounds="()")
    resource = ForeignKey(
        Resource,
        verbose_name=_("Resource"),
        on_delete=PROTECT,
        related_name="bookings_of_resource",
        related_query_name="booking_of_resource",
    )
    status = IntegerField(verbose_name=_("Status"), choices=BookingStatus.choices)
    booking_series = ForeignKey(
        BookingSeries,
        verbose_name=_("Booking series"),
        on_delete=CASCADE,
        related_name="bookings_of_bookingseries",
        related_query_name="booking_of_bookingseries",
        null=True,
        blank=True,
    )
    # These fields are only stored for potential DST (Dailight Saving Time) problems.
    start_date = DateField(_("Start date"))
    end_date = DateField(_("End date"))
    start_time = TimeField(_("Start time"))
    end_time = TimeField(_("End time"))

    compensation = ForeignKey(
        Compensation,
        verbose_name=_("Compensation"),
        on_delete=PROTECT,
        related_name="bookings_of_compensation",
        related_query_name="booking_of_compensation",
    )
    total_amount = DecimalField(
        _("Total amount"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    invoice_number = CharField(_("Invoice number"), max_length=160, blank=True)
    invoice_address = CharField(_("Invoice address"), blank=True, max_length=256)
    number_of_attendees = PositiveIntegerField(_("Number of attendees"), default=5)
    activity_description = CharField(
        _("Activity description"),
        help_text=_("Please describe shortly what you are planning to do."),
        max_length=2048,
    )
    auto_generated_on = DateTimeField(
        _("Automatically generated on"), blank=True, null=True
    )
    import_id = CharField(
        _("Import ID"),
        help_text=_(
            "The ID of the record in the old system. This is used for referencing "
            "records even after migration."
        ),
        max_length=256,
        blank=True,
    )

    class Meta:
        verbose_name = _("Booking")
        verbose_name_plural = _("Bookings")
        ordering = ["timespan"]
        indexes = [
            GistIndex(fields=["timespan"]),
            Index(fields=["resource"]),
            Index(fields=["organization"]),
            Index(fields=["booking_series"]),
        ]

        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_reservations",
                violation_error_message=_(
                    "The requested timespan overlaps with an existing booking for this "
                    "resource. Please chose another timespan.",
                ),
                expressions=[
                    ("timespan", RangeOperators.OVERLAPS),
                    ("resource", RangeOperators.EQUAL),
                ],
                condition=Q(status=2),  # 2 = CONFIRMED
            ),
        ]

    def __str__(self):
        return str(self.slug)

    def get_absolute_url(self):
        return reverse("bookings:show-booking", kwargs={"booking": self.slug})

    def end_is_in_the_past(self):
        return self.timespan.upper < timezone.now()

    def start_is_in_the_past(self):
        return self.timespan.lower < timezone.now()

    def is_cancelable(self):
        return not self.start_is_in_the_past() and self.status not in [
            BookingStatus.CANCELLED,
            BookingStatus.UNAVAILABLE,
        ]

    def is_editable(self):
        return not self.end_is_in_the_past() and self.status not in [
            BookingStatus.CANCELLED,
            BookingStatus.UNAVAILABLE,
        ]

    def is_confirmable(self):
        return not self.end_is_in_the_past() and self.status == BookingStatus.PENDING


class BookingMessage(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    booking = ForeignKey(
        Booking,
        verbose_name=_("Booking"),
        on_delete=CASCADE,
        related_name="bookingmessages_of_booking",
        related_query_name="bookingmessage_of_booking",
    )
    text = CharField(_("Message"), max_length=800)
    user = ForeignKey(
        User,
        verbose_name=_("User"),
        on_delete=PROTECT,
        related_name="bookingmessages_of_user",
        related_query_name="bookingmessage_of_user",
    )

    class Meta:
        verbose_name = _("Booking Message")
        verbose_name_plural = _("Booking Messages")
        ordering = ["created"]

    def get_absolute_url(self):
        return reverse("bookings:show-booking", kwargs={"booking": self.booking.slug})


auditlog.register(Booking, exclude_fields=["created, updated"])
auditlog.register(BookingSeries, exclude_fields=["created, updated"])
