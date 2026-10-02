"""
Pricing of bookings against the free bookings allowance of an organization.

Shared by single bookings (services.py) and booking series
(services_booking_series.py), which cannot import each other.
"""

from datetime import date
from datetime import datetime

from django.utils.translation import gettext_lazy as _

from re_sharing.organizations.selectors import get_remaining_free_bookings
from re_sharing.organizations.selectors import is_free_bookings_allowance_limited_until
from re_sharing.resources.selectors import get_paid_fallback_compensations


class FreeBookingsExhaustedError(Exception):
    """A booking cannot be priced because no free booking of its year is left."""

    def __init__(self, year):
        self.year = year
        self.message = _(
            "No free bookings left for %(year)s. Please choose another compensation."
        ) % {"year": year}
        super().__init__(self.message)


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


def _timespan_bounds(timespan):
    if isinstance(timespan, tuple):
        return timespan
    return timespan.lower, timespan.upper


def _hourly_total(booking, compensation):
    if compensation.hourly_rate is None:
        return None
    start, end = _timespan_bounds(booking.timespan)
    return (end - start).total_seconds() / 3600 * compensation.hourly_rate


def needs_quota_reevaluation(booking, organization, compensation, start_date):
    """
    Whether a booking has to be priced against the free bookings allowance.

    New bookings always are. An existing booking only when its organization,
    its compensation or the calendar year of its start date changes, so that
    other edits keep whether the booking is free.
    """
    if booking is None or booking.pk is None:
        return True
    return (
        booking.organization_id != organization.pk
        or booking.compensation_id != compensation.pk
        or booking.start_date.year != _as_date(start_date).year
    )


def price_booking(
    booking,
    compensation,
    fallback_compensation=None,
    exclude_booking=None,
    reserved=0,
):
    """
    Set compensation, total_amount and uses_free_booking on an unsaved booking.

    A compensation that counts against free bookings is kept while the
    organization has a free booking left in the year of the booking's start
    date; the booking is then free and marked as using one. Otherwise the
    fallback compensation is charged for the full duration, or, without one,
    FreeBookingsExhaustedError is raised. ``reserved`` free bookings of the
    same year that are not saved yet (earlier occurrences of a series) are
    treated as used.
    """
    booking.compensation = compensation
    booking.uses_free_booking = False
    if compensation.counts_against_free_bookings:
        quota_date = _as_date(booking.start_date)
        remaining = get_remaining_free_bookings(
            booking.organization, quota_date, exclude_booking=exclude_booking
        )
        if remaining is not None:
            if remaining - reserved >= 1:
                booking.uses_free_booking = True
                booking.total_amount = None
                return booking
            if fallback_compensation is None:
                raise FreeBookingsExhaustedError(quota_date.year)
            booking.compensation = fallback_compensation
    booking.total_amount = _hourly_total(booking, booking.compensation)
    return booking


def get_free_bookings_remaining_after(booking):
    """
    Free bookings of the booking's year that are left once it is saved.
    ``None`` when the booking uses none or the allowance is unlimited.
    """
    if not booking.uses_free_booking:
        return None
    remaining = get_remaining_free_bookings(
        booking.organization,
        _as_date(booking.start_date),
        exclude_booking=booking if booking.pk else None,
    )
    if remaining is None:
        return None
    return max(remaining - 1, 0)


def get_usable_fallback_compensation(booking_series):
    """
    The series' fallback compensation if it can still be used: active, with an
    hourly rate and bookable by the organization for the resource. Otherwise
    ``None``, so occurrences beyond the allowance are dropped (D6).
    """
    fallback = booking_series.fallback_compensation
    if fallback is None:
        return None
    usable = get_paid_fallback_compensations(
        booking_series.organization, booking_series.resource
    ).filter(pk=fallback.pk)
    return fallback if usable.exists() else None


def series_needs_fallback(organization, resource, compensation, last_date):
    """
    Whether a series with this compensation must name a fallback: the
    compensation counts against free bookings, the allowance is limited on
    some occurrence date up to ``last_date`` and a paid compensation exists.
    """
    if compensation is None or not compensation.counts_against_free_bookings:
        return False
    if not is_free_bookings_allowance_limited_until(organization, last_date):
        return False
    return get_paid_fallback_compensations(organization, resource).exists()
