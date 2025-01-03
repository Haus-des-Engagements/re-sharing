import concurrent
import re
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
from django.db.models import Q
from django.shortcuts import get_list_or_404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware
from django_q.tasks import async_task

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import get_booking_status

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
    bs.total_amount_per_occurrence = None
    bs.activity_description = booking_data["activity_description"]
    if booking_data["compensation"]:
        bs.compensation = get_object_or_404(
            Compensation, id=booking_data["compensation"]
        )
        if bs.compensation.hourly_rate is not None:
            duration_hours = (timespan[1] - timespan[0]).total_seconds() / 3600
            bs.total_amount_per_occurrence = (
                duration_hours * bs.compensation.hourly_rate
            )

    if "COUNT" not in bs.rrule and "UNTIL" not in bs.rrule:
        bs.last_booking_date = None
    else:
        bs.last_booking_date = list(rrulestr(bs.rrule))[-1]

    # Generate occurrences
    max_booking_date = timezone.now().date() + timedelta(days=max_future_booking_date)
    max_booking_datetime = make_aware(
        datetime.combine(max_booking_date, bs.end_time)
    ).astimezone(UTC)
    bookings = generate_bookings(bs, bs.first_booking_date, max_booking_datetime)

    # Determine if resource is at least once bookable
    bookable = any(booking.status != BookingStatus.UNAVAILABLE for booking in bookings)
    return bookings, bs, bookable


def save_booking_series(user, bookings, booking_series):
    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied
    if user.is_staff:
        booking_series.status = BookingStatus.CONFIRMED
    booking_series.save()
    for booking in bookings:
        booking.save()

    async_task(
        "re_sharing.organizations.mails.manager_new_recurrence",
        rrule,
        task_name="manager-new-recurrence",
    )

    return bookings, booking_series


def cancel_bookings_of_booking_series(user, booking_series_uuid):
    bs = get_object_or_404(BookingSeries, uuid=booking_series_uuid)
    bookings = get_list_or_404(Booking, booking_series=bs)

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    bs.status = BookingStatus.CANCELLED
    bs.save()

    for booking in bookings:
        if booking.is_cancelable():
            with set_actor(user):
                booking.status = BookingStatus.CANCELLED
                booking.save()

    return bs


def get_booking_series_list(user):
    organizations = organizations_with_confirmed_bookingpermission(user)
    return BookingSeries.objects.filter(
        booking_of_bookingseries__organization__in=organizations
    ).distinct()


def get_bookings_of_booking_series(user, booking_series_slug):
    bs = get_object_or_404(BookingSeries, slug=booking_series_slug)
    bookings = get_list_or_404(Booking, booking_series=bs)

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    is_cancelable = bs.is_cancelable()
    return bs, bookings, is_cancelable


def manager_filter_booking_series_list(organization, show_past_rrules, status):
    organizations = Organization.objects.all()
    bs_set = BookingSeries.objects.all().distinct()
    if not show_past_rrules:
        bs_set = bs_set.filter(
            Q(last_occurrence_date__gte=timezone.now())
            | Q(last_occurrence_date__isnull=True)
        )
    if organization != "all":
        bs_set = bs_set.filter(
            booking_of_bookingseries__organization__slug=organization
        )
    if status != "all":
        bs_set = bs_set.filter(status=status)
    bs_set = bs_set.order_by("created")

    return bs_set, organizations


def manager_cancel_booking_series(user, booking_series_uuid):
    bs = get_object_or_404(BookingSeries, uuid=booking_series_uuid)
    bookings = get_list_or_404(Booking, booking_series=bs)
    bs.status = BookingStatus.CANCELLED
    bs.save()

    for booking in bookings:
        if booking.is_cancelable():
            with set_actor(user):
                booking.status = BookingStatus.CANCELLED
                booking.save()

    async_task(
        "re_sharing.organizations.mails.recurrence_cancellation_email",
        rrule,
        task_name="recurrence-cancellation-email",
    )
    return rrule


def extend_booking_series():
    max_booking_date = timezone.now().date() + timedelta(
        days=max_future_booking_date + 1
    )
    first_second = time(hour=0, minute=0, second=0)
    start_new_bookings_at = make_aware(
        datetime.combine(max_booking_date, first_second)
    ).astimezone(UTC)

    last_second = time(hour=23, minute=59, second=59)
    end_new_bookings_at = datetime.combine(max_booking_date, last_second).astimezone(
        UTC
    )

    bs_set = BookingSeries.objects.filter(
        Q(last_occurrence_date=None)
        | Q(last_occurrence_date__gte=start_new_bookings_at)
    ).filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
    bs_set = bs_set.order_by("created")
    new_bookings = []
    for bs in bs_set:
        # generate bookings that are after max booking date and before target date
        bookings = generate_bookings(bs, start_new_bookings_at, end_new_bookings_at)
        for current_booking in bookings:
            # Determine if the current booking stems from the same booking_series and "
            # thus should not be saved
            is_same_booking_series = (
                current_booking.status == BookingStatus.UNAVAILABLE
                and Booking.objects.filter(resource=bs.resource)
                .filter(timespan__overlap=current_booking.timespan)
                .filter(booking_series=bs)
                .exists()
            )
            if not is_same_booking_series:
                current_booking.save()
                new_bookings.append(current_booking)

    return new_bookings


def generate_bookings(booking_series, start, end):
    last_occurrence_before_end = rrulestr(booking_series.rrule).before(end, inc=True)
    occurrences = list(
        rrulestr(booking_series.rrule).between(
            start, last_occurrence_before_end, inc=True
        )
    )

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
            total_amount=booking_series.total_amount_per_occurrence,
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
        return list(executor.map(create_booking_series_booking, occurrences))
