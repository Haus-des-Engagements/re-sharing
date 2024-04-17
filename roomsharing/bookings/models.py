import uuid

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.contrib.postgres.fields import RangeOperators
from django.db.models import PROTECT
from django.db.models import CharField
from django.db.models import ForeignKey
from django.db.models import Model
from django.db.models import UUIDField
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
from roomsharing.users.models import User


class BookingGroup(Model):
    title = CharField(_("Title"), max_length=160)
    slug = AutoSlugField(populate_from="title")
    organization = ForeignKey(
        Organization,
        verbose_name=_("Booking Organization"),
        on_delete=PROTECT,
        related_name="bookinggroups_of_organization",
        related_query_name="bookinggroup_of_organization",
    )
    user = ForeignKey(
        User,
        verbose_name=_("Initial Booking User"),
        on_delete=PROTECT,
        related_name="bookinggroups_of_user",
        related_query_name="bookinggroup_of_user",
    )

    class Meta:
        verbose_name = _("Booking Group")
        verbose_name_plural = _("Booking Groups")
        ordering = ["title"]

    def __str__(self):
        return self.title


class Booking(Model):
    uuid = UUIDField(
        db_index=True,
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    timespan = DateTimeRangeField("Date Time Range", default_bounds="()")
    room = ForeignKey(
        Room,
        verbose_name=_("Room"),
        on_delete=PROTECT,
        related_name="bookings_of_room",
        related_query_name="booking_of_room",
    )
    booking_group = ForeignKey(
        BookingGroup,
        verbose_name=_("Booking Group"),
        on_delete=PROTECT,
        related_name="bookings_of_bookinggroup",
        related_query_name="booking_of_bookinggroup",
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
            ),
        ]

    def __str__(self):
        return str(self.uuid)
