from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields import RangeOperators
from django.db.models import PROTECT
from django.db.models import CharField
from django.db.models import ForeignKey
from django.db.models import IntegerChoices
from django.db.models import IntegerField
from django.db.models import Model
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
from roomsharing.users.models import User


class Booking(Model):
    class Status(IntegerChoices):
        PENDING = 1, _("Pending")
        CONFIRMED = 2, _("Confirmed")
        CANCELLED = 3, _("Cancelled")

    title = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from="title")
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
    status = IntegerField(choices=Status.choices)

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
