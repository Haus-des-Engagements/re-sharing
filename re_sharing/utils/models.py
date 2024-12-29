from django.db import models
from django.db.models import IntegerChoices
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    # See https://docs.djangoproject.com/en/3.0/ref/models/fields/#django.db.models
    # .DateField for attributes.
    created = models.DateTimeField(
        verbose_name=_("Created"),
        auto_now_add=True,
        editable=False,
        blank=True,
    )
    updated = models.DateTimeField(
        verbose_name=_("Updated"),
        auto_now=True,
        editable=False,
        blank=True,
    )

    class Meta:
        abstract = True


class BookingStatus(IntegerChoices):
    PENDING = 1, _("Pending")
    CONFIRMED = 2, _("Confirmed")
    CANCELLED = 3, _("Cancelled")
    UNAVAILABLE = 4, _("Unavailable")


def get_booking_status(user, organization, resource):
    if user.is_staff or user.is_superuser:
        return BookingStatus.CONFIRMED
    if organization.organization_groups.filter(
        auto_confirmed_resources=resource
    ).exists():
        return BookingStatus.CONFIRMED
    if user.usergroups_of_user.filter(auto_confirmed_resources=resource).exists():
        return BookingStatus.CONFIRMED
    return BookingStatus.PENDING
