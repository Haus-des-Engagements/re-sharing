from auditlog.models import AuditlogHistoryField
from auditlog.registry import auditlog
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields import RangeOperators
from django.db.models import PROTECT
from django.db.models import CharField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
from roomsharing.users.models import User
from roomsharing.utils.models import TimeStampedModel


class Booking(TimeStampedModel):
    history = AuditlogHistoryField()

    class Status(IntegerChoices):
        PENDING = 1, _("Pending")
        CONFIRMED = 2, _("Confirmed")
        CANCELLED = 3, _("Cancelled")

    title = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from="title", editable=False)
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
    status = IntegerField(verbose_name=_("Status"), choices=Status.choices)

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
        return reverse("bookings:detail", kwargs={"slug": self.slug})


class BookingMessage(TimeStampedModel):
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
        return reverse("bookings:detail", kwargs={"slug": self.booking.slug})


auditlog.register(Booking, exclude_fields=["created, updated"])
