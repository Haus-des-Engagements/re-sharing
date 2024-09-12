import uuid

from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from dateutil.rrule import rrulestr
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields import RangeOperators
from django.db.models import CASCADE
from django.db.models import PROTECT
from django.db.models import SET_NULL
from django.db.models import CharField
from django.db.models import DateField
from django.db.models import DecimalField
from django.db.models import ForeignKey
from django.db.models import IntegerField
from django.db.models import Q
from django.db.models import TimeField
from django.db.models import UUIDField
from django.urls import reverse
from django.utils import formats
from django.utils import timezone
from django.utils.dates import WEEKDAYS
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Compensation
from roomsharing.rooms.models import Room
from roomsharing.users.models import User
from roomsharing.utils.dicts import RRULE_DAILY_INTERVAL
from roomsharing.utils.dicts import RRULE_MONTHLY_INTERVAL
from roomsharing.utils.dicts import RRULE_WEEKLY_INTERVAL
from roomsharing.utils.models import BookingStatus
from roomsharing.utils.models import TimeStampedModel


class RecurrenceRule(TimeStampedModel):
    history = AuditlogHistoryField()
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    rrule = CharField(_("Recurrence rule"), max_length=200)
    first_occurrence_date = DateField(_("First occurrence date"))
    last_occurrence_date = DateField(_("Last occurrence date"))
    excepted_dates = ArrayField(
        DateField(), verbose_name=_("Excepted dates"), blank=True
    )

    class Meta:
        verbose_name = _("Recurrence rule")
        verbose_name_plural = _("Recurrence rules")
        ordering = ["created"]

    def __str__(self):
        return str(self.uuid)

    def get_absolute_url(self):
        return reverse("bookings:show-recurrence", kwargs={"rrule": self.uuid})

    def number_of_occurrences(self):
        return self.bookings_of_recurrencerule.count()

    def get_first_booking(self):
        return self.bookings_of_recurrencerule.first()

    def is_cancelable(self):
        return any(
            booking.is_cancelable() for booking in self.bookings_of_recurrencerule.all()
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

        date_string = formats.date_format(rrule._until.date(), "SHORT_DATE_FORMAT")  # noqa: SLF001
        return _("ends at the ") + date_string

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
    room = ForeignKey(
        Room,
        verbose_name=_("Room"),
        on_delete=PROTECT,
        related_name="bookings_of_room",
        related_query_name="booking_of_room",
    )
    status = IntegerField(verbose_name=_("Status"), choices=BookingStatus.choices)
    recurrence_rule = ForeignKey(
        RecurrenceRule,
        verbose_name=_("Recurrence rule"),
        on_delete=CASCADE,
        related_name="bookings_of_recurrencerule",
        related_query_name="booking_of_recurrencerule",
        null=True,
        blank=True,
    )
    # These fields are only stored for potential DST (Dailight Saving Time) problems.
    start_date = DateField(_("Start Date"))
    start_time = TimeField(_("Start Time"))
    end_time = TimeField(_("End Time"))

    compensation = ForeignKey(
        Compensation,
        verbose_name=_("Compensation"),
        on_delete=SET_NULL,
        related_name="bookings_of_compensation",
        related_query_name="booking_of_compensation",
        null=True,
        blank=True,
    )
    total_amount = DecimalField(
        _("Total Amount"),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Booking")
        verbose_name_plural = _("Bookings")
        ordering = ["timespan"]
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping_reservations",
                violation_error_message=_(
                    "The requested timespan overlaps with an existing booking for this "
                    "room. Please chose another timespan.",
                ),
                expressions=[
                    ("timespan", RangeOperators.OVERLAPS),
                    ("room", RangeOperators.EQUAL),
                ],
                condition=Q(status=2),  # 2 = CONFIRMED
            ),
        ]

    def __str__(self):
        return str(self.title)

    def get_absolute_url(self):
        return reverse("bookings:show-booking", kwargs={"booking": self.slug})

    def is_in_the_past(self):
        return self.timespan.lower < timezone.now()

    def is_cancelable(self):
        return not self.is_in_the_past() and self.status != BookingStatus.CANCELLED

    def is_confirmable(self):
        return not self.is_in_the_past() and self.status == BookingStatus.PENDING


class BookingMessage(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    history = AuditlogHistoryField()
    booking = ForeignKey(
        Booking,
        verbose_name=_("Booking"),
        on_delete=PROTECT,
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
auditlog.register(BookingMessage, exclude_fields=["created, updated"])
auditlog.register(RecurrenceRule, exclude_fields=["created, updated"])
