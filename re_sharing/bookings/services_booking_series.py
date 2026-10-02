import concurrent
import logging
import re
from collections import defaultdict
from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta

from auditlog.context import set_actor
from dateutil.parser import isoparse
from dateutil.rrule import DAILY
from dateutil.rrule import FR
from dateutil.rrule import MO
from dateutil.rrule import MONTHLY
from dateutil.rrule import SA
from dateutil.rrule import SU
from dateutil.rrule import TH
from dateutil.rrule import TU
from dateutil.rrule import WE
from dateutil.rrule import WEEKLY
from dateutil.rrule import rrule
from dateutil.rrule import rrulestr
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_list_or_404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services_pricing import FreeBookingsExhaustedError
from re_sharing.bookings.services_pricing import get_usable_fallback_compensation
from re_sharing.bookings.services_pricing import price_booking
from re_sharing.bookings.services_pricing import series_needs_fallback
from re_sharing.organizations.mails import send_booking_series_cancellation_email
from re_sharing.organizations.mails import send_manager_new_booking_series_email
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.selectors import get_paid_fallback_compensations
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import get_booking_status

logger = logging.getLogger(__name__)

max_future_booking_date = 730


def create_rrule(rrule_data):
    rrule_repetitions = rrule_data["rrule_repetitions"]
    rrule_ends = rrule_data["rrule_ends"]
    rrule_ends_count = rrule_data.get("rrule_ends_count")
    rrule_ends_enddate = rrule_data.get("rrule_ends_enddate")
    rrule_daily_interval = rrule_data["rrule_daily_interval"]
    rrule_weekly_interval = rrule_data["rrule_weekly_interval"]
    rrule_weekly_byday = rrule_data["rrule_weekly_byday"]
    rrule_monthly_interval = rrule_data["rrule_monthly_interval"]
    rrule_monthly_bydate = rrule_data["rrule_monthly_bydate"]
    rrule_monthly_byday = rrule_data["rrule_monthly_byday"]
    start = rrule_data["start"].astimezone(UTC)

    if rrule_ends == "AFTER_TIMES":
        count = rrule_ends_count
        rrule_enddate = None
    elif rrule_ends == "NEVER":
        count = None
        rrule_enddate = None
    else:
        count = None
        rrule_enddate = rrule_ends_enddate.astimezone(UTC)

    byweekday, bymonthday = None, None
    weekdays_dict = {
        "MO": MO,
        "TU": TU,
        "WE": WE,
        "TH": TH,
        "FR": FR,
        "SA": SA,
        "SU": SU,
    }

    if rrule_repetitions == "DAILY":
        interval = rrule_daily_interval

    if rrule_repetitions == "WEEKLY":
        interval = rrule_weekly_interval
        byweekday = rrule_weekly_byday
        byweekday = [weekdays_dict.get(day) for day in byweekday]

    if rrule_repetitions == "MONTHLY_BY_DAY":
        interval = rrule_monthly_interval
        byweekday_str = rrule_monthly_byday
        byweekday = []
        for day in byweekday_str:
            weekday, week_number = day.split("(")
            week_number = int(week_number.strip(")"))
            byweekday.append(weekdays_dict[weekday](week_number))

    if rrule_repetitions == "MONTHLY_BY_DATE":
        interval = rrule_monthly_interval
        bymonthday_str = rrule_monthly_bydate
        bymonthday = [int(x) for x in bymonthday_str]

    frequency_dict = {
        "DAILY": DAILY,
        "WEEKLY": WEEKLY,
        "MONTHLY_BY_DAY": MONTHLY,
        "MONTHLY_BY_DATE": MONTHLY,
    }

    recurrence_pattern = rrule(
        frequency_dict[rrule_repetitions],
        interval=interval,
        byweekday=byweekday,
        bymonthday=bymonthday,
        dtstart=start,
        bysetpos=None,
        until=rrule_enddate,
        count=count,
    )
    # hacky way of getting the timzone ("Z") into dtstart and UNTIL
    unmodified_str = str(recurrence_pattern)
    # Add 'Z' before line break
    modified_string = re.sub(r"(\n)", "Z\\1", unmodified_str)
    if rrule_enddate:
        # Add 'Z' after UNTIL value
        modified_string = re.sub(r"(UNTIL=[0-9T]+)(;|$)", r"\1Z\2", modified_string)
    return str(modified_string)


def create_booking_series_and_bookings(booking_data):
    timespan = (
        isoparse(booking_data["timespan"][0]),
        isoparse(booking_data["timespan"][1]),
    )

    bs = BookingSeries()
    bs.user = get_object_or_404(User, slug=booking_data["user"])
    bs.title = booking_data["title"]
    bs.resource = get_object_or_404(Resource, slug=booking_data["resource"])
    bs.organization = get_object_or_404(Organization, slug=booking_data["organization"])
    bs.status = get_booking_status(bs.user, bs.organization, bs.resource)
    bs.start_time = datetime.strptime(booking_data["start_time"], "%H:%M:%S").time()  # noqa: DTZ007
    bs.end_time = datetime.strptime(booking_data["end_time"], "%H:%M:%S").time()  # noqa: DTZ007
    bs.rrule = booking_data.get("rrule_string", "")
    bs.first_booking_date = next(iter(rrulestr(bs.rrule)))
    bs.invoice_address = booking_data["invoice_address"]
    bs.compensation = None
    bs.total_amount_per_booking = None
    bs.activity_description = booking_data["activity_description"]
    bs.reminder_emails = booking_data.get("reminder_emails", True)
    # new series are priced occurrence by occurrence against the free bookings
    bs.is_quota_priced = True
    bs.fallback_compensation = None
    if booking_data.get("fallback_compensation"):
        bs.fallback_compensation = get_object_or_404(
            Compensation, id=booking_data["fallback_compensation"]
        )
    if booking_data["compensation"]:
        bs.compensation = get_object_or_404(
            Compensation, id=booking_data["compensation"]
        )
        if bs.compensation.hourly_rate is not None:
            duration_hours = (timespan[1] - timespan[0]).total_seconds() / 3600
            bs.total_amount_per_booking = duration_hours * bs.compensation.hourly_rate

    if "COUNT" not in bs.rrule and "UNTIL" not in bs.rrule:
        bs.last_booking_date = None
    else:
        bs.last_booking_date = list(rrulestr(bs.rrule))[-1]

    # Generate occurrences
    max_booking_date = timezone.now().date() + timedelta(days=max_future_booking_date)
    max_booking_datetime = make_aware(
        datetime.combine(max_booking_date, bs.end_time)
    ).astimezone(UTC)
    occurrences = get_series_occurrences(
        bs, bs.first_booking_date, max_booking_datetime
    )
    bookings = generate_bookings(bs, bs.first_booking_date, max_booking_datetime)
    pricing = summarize_series_pricing(bs, bookings, len(occurrences))

    # Determine if resource is at least once bookable
    bookable = any(booking.status != BookingStatus.UNAVAILABLE for booking in bookings)
    return bookings, bs, bookable, pricing


def summarize_series_pricing(booking_series, bookings, occurrence_count):
    """Breakdown of a series' occurrences for the preview."""
    free = sum(1 for booking in bookings if booking.uses_free_booking)
    unavailable = sum(
        1 for booking in bookings if booking.status == BookingStatus.UNAVAILABLE
    )
    paid_bookings = [
        booking
        for booking in bookings
        if booking.status != BookingStatus.UNAVAILABLE and booking.total_amount
    ]
    fallback = booking_series.fallback_compensation
    return {
        "free": free,
        "paid": len(paid_bookings),
        "unavailable": unavailable,
        "dropped": occurrence_count - len(bookings),
        "rate": fallback.hourly_rate if fallback is not None else None,
        "total": sum(booking.total_amount for booking in paid_bookings),
    }


def _validate_series_fallback(booking_series):
    """The fallback comes from the session, not from a validated form."""
    paid_compensations = get_paid_fallback_compensations(
        booking_series.organization, booking_series.resource
    )
    fallback = booking_series.fallback_compensation
    if fallback is not None and not paid_compensations.filter(pk=fallback.pk).exists():
        raise PermissionDenied
    horizon = timezone.now().date() + timedelta(days=max_future_booking_date)
    last_date = booking_series.last_booking_date
    last_date = min(last_date.date(), horizon) if last_date is not None else horizon
    if fallback is None and series_needs_fallback(
        booking_series.organization,
        booking_series.resource,
        booking_series.compensation,
        last_date,
    ):
        raise PermissionDenied


def save_booking_series(user, bookings, booking_series):
    from re_sharing.bookings.services import is_bookable_by_organization

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    with transaction.atomic():
        # Series of one organization are serialized on its row, so the stored
        # prices reflect the free bookings left at the time of saving.
        Organization.objects.select_for_update().get(pk=booking_series.organization_id)
        if not is_bookable_by_organization(
            user,
            booking_series.organization,
            booking_series.resource,
            booking_series.compensation,
            start_date=booking_series.first_booking_date,
            is_series=True,
        ):
            raise PermissionDenied
        _validate_series_fallback(booking_series)
        bookings, _dropped = price_series_bookings(booking_series, bookings)

        if user.is_manager():
            booking_series.status = BookingStatus.CONFIRMED
        booking_series.save()
        for booking in bookings:
            booking.user = booking_series.user
            booking.save()
    send_manager_new_booking_series_email.enqueue(booking_series.id)

    return bookings, booking_series


def cancel_bookings_of_booking_series(user, booking_series_uuid):
    bs = get_object_or_404(BookingSeries, uuid=booking_series_uuid)
    bookings = get_list_or_404(Booking, booking_series=bs)

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    bs.status = BookingStatus.CANCELLED
    bs.save()

    now = timezone.now()
    for booking in bookings:
        # Delete future bookings, keep past bookings
        if booking.timespan.lower > now:
            with set_actor(user):
                booking.delete()
    return bs


def get_booking_series_list(user):
    organizations = organizations_with_confirmed_bookingpermission(user)
    return BookingSeries.objects.filter(
        booking_of_bookingseries__organization__in=organizations
    ).distinct()


def get_bookings_of_booking_series(user, booking_series_slug):
    bs = get_object_or_404(BookingSeries, slug=booking_series_slug)
    bookings = Booking.objects.select_related("resource").filter(booking_series=bs)

    if bookings and not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    is_cancelable = bs.is_cancelable()
    return bs, bookings, is_cancelable


def manager_filter_booking_series_list(
    organization_search, show_past_booking_series, status
):
    bs_list = BookingSeries.objects.all().distinct()
    if not show_past_booking_series:
        bs_list = bs_list.filter(
            Q(last_booking_date__gte=timezone.now()) | Q(last_booking_date__isnull=True)
        )
    if organization_search:
        bs_list = bs_list.filter(
            booking_of_bookingseries__organization__name__icontains=organization_search
        )
    if status != "all":
        bs_list = bs_list.filter(status=status)

    return bs_list.order_by("created")


def manager_cancel_booking_series(user, booking_series_uuid):
    from re_sharing.resources.services_nuki import sync_all_smartlock_codes

    booking_series = get_object_or_404(BookingSeries, uuid=booking_series_uuid)
    bookings = get_list_or_404(Booking, booking_series=booking_series)
    booking_series.status = BookingStatus.CANCELLED
    booking_series.save()

    # Check if any today's confirmed bookings have smartlock access
    today = timezone.now().date()
    should_sync_smartlocks = False
    for booking in bookings:
        if (
            booking.status == BookingStatus.CONFIRMED
            and booking.timespan.lower.date() == today
            and booking.resource.access
        ):
            access = booking.resource.access
            if access.smartlock_id or (
                access.parent_access and access.parent_access.smartlock_id
            ):
                should_sync_smartlocks = True
                break

    now = timezone.now()
    for booking in bookings:
        if booking.is_cancelable():
            # Delete future bookings, keep past bookings
            if booking.timespan.upper and booking.timespan.upper > now:
                with set_actor(user):
                    booking.delete()
            else:
                # Past bookings are just cancelled, not deleted
                with set_actor(user):
                    booking.status = BookingStatus.CANCELLED
                    booking.save()

    send_booking_series_cancellation_email.enqueue(booking_series.id)

    if should_sync_smartlocks:
        sync_all_smartlock_codes.enqueue()

    return booking_series


def extend_booking_series():
    max_booking_date = timezone.now().date() + timedelta(
        days=max_future_booking_date + 1
    )
    first_second = time(hour=0, minute=0, second=0)
    start_new_bookings_at = datetime.combine(max_booking_date, first_second, tzinfo=UTC)

    last_second = time(hour=23, minute=59, second=59)
    end_new_bookings_at = datetime.combine(max_booking_date, last_second, tzinfo=UTC)

    bs_set = (
        BookingSeries.objects.filter(
            Q(last_booking_date=None) | Q(last_booking_date__gte=start_new_bookings_at)
        )
        .filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
        .select_related(
            "user", "resource", "organization", "compensation", "fallback_compensation"
        )
    )
    bs_set = bs_set.order_by("created")
    new_bookings = []
    for bs in bs_set:
        # Each series gets its own transaction, so one failing series does not
        # roll back or stop the others.
        try:
            new_bookings.extend(
                generate_and_save_bookings(
                    bs, start_new_bookings_at, end_new_bookings_at
                )
            )
        except Exception:
            logger.exception("Could not extend booking series %s", bs.pk)

    return new_bookings


def generate_and_save_bookings(booking_series, start, end):
    """
    Generate and store the occurrences of one series between ``start`` and
    ``end`` under the organization's lock. Used by the nightly extension and
    the admin action.
    """
    saved = []
    with transaction.atomic():
        Organization.objects.select_for_update().get(pk=booking_series.organization_id)
        bookings = generate_bookings(booking_series, start, end)
        for current_booking in bookings:
            # Determine if the current booking stems from the same booking_series
            # and thus should not be saved
            is_same_booking_series = (
                current_booking.status == BookingStatus.UNAVAILABLE
                and Booking.objects.filter(resource=booking_series.resource)
                .filter(timespan__overlap=current_booking.timespan)
                .filter(booking_series=booking_series)
                .exists()
            )
            if not is_same_booking_series:
                current_booking.save()
                saved.append(current_booking)
    return saved


def get_series_occurrences(booking_series, start, end):
    last_occurrence_before_end = rrulestr(booking_series.rrule).before(end, inc=True)
    return list(
        rrulestr(booking_series.rrule).between(
            start, last_occurrence_before_end, inc=True
        )
    )


def price_series_bookings(booking_series, bookings):
    """
    Price the occurrences of a quota-priced series in date order against the
    allowance of their own year. Occurrences that can neither use a free
    booking nor be charged with the fallback are left out. Returns the kept
    occurrences and the number of dropped ones.
    """
    fallback = get_usable_fallback_compensation(booking_series)
    reserved = defaultdict(int)
    kept = []
    dropped = 0
    for booking in sorted(bookings, key=lambda booking: booking.start_date):
        if booking.status == BookingStatus.UNAVAILABLE:
            # not priced, the room is taken
            booking.compensation = booking_series.compensation
            booking.total_amount = booking_series.total_amount_per_booking
            booking.uses_free_booking = False
            kept.append(booking)
            continue
        year = booking.start_date.year
        try:
            price_booking(
                booking,
                booking_series.compensation,
                fallback_compensation=fallback,
                reserved=reserved[year],
            )
        except FreeBookingsExhaustedError:
            dropped += 1
            continue
        if booking.uses_free_booking:
            reserved[year] += 1
        kept.append(booking)
    return kept, dropped


def generate_bookings(booking_series, start, end):
    occurrences = get_series_occurrences(booking_series, start, end)

    # Helper function to create a booking
    def create_booking_series_booking(occurrence):
        booking_start = timezone.make_aware(
            datetime.combine(occurrence, booking_series.start_time)
        )
        booking_end = timezone.make_aware(
            datetime.combine(occurrence, booking_series.end_time)
        )
        timespan = (booking_start, booking_end)
        booking = Booking(
            title=booking_series.title,
            user=booking_series.user,
            resource=booking_series.resource,
            timespan=timespan,
            organization=booking_series.organization,
            status=booking_series.status,
            start_date=occurrence.date(),
            start_time=booking_series.start_time,
            end_date=occurrence.date(),
            end_time=booking_series.end_time,
            compensation=booking_series.compensation,
            total_amount=booking_series.total_amount_per_booking,
            booking_series=booking_series,
            auto_generated_on=timezone.now(),
            invoice_address=booking_series.invoice_address,
            activity_description=booking_series.activity_description,
        )
        if booking.resource.is_booked(booking.timespan):
            booking.status = BookingStatus.UNAVAILABLE
        return booking

    # Create bookings in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        bookings = list(executor.map(create_booking_series_booking, occurrences))

    # Series created before the free bookings limit keep the series pricing
    if not booking_series.is_quota_priced:
        return bookings
    kept, _dropped = price_series_bookings(booking_series, bookings)
    return kept
