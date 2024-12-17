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

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import RecurrenceRule
from roomsharing.organizations.models import Organization
from roomsharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from roomsharing.organizations.services import user_has_bookingpermission
from roomsharing.rooms.models import Compensation
from roomsharing.rooms.models import Room
from roomsharing.users.models import User
from roomsharing.utils.models import BookingStatus

max_future_booking_date = 730


def create_rrule_string(rrule_data):
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
    start_datetime = rrule_data["start_datetime"].astimezone(UTC)

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
        dtstart=start_datetime,
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


def create_rrule_and_occurrences(booking_data):
    message = booking_data["message"]
    timespan = (
        isoparse(booking_data["timespan"][0]),
        isoparse(booking_data["timespan"][1]),
    )

    rrule = RecurrenceRule()
    rrule.user = get_object_or_404(User, slug=booking_data["user"])
    rrule.title = booking_data["title"]
    rrule.room = get_object_or_404(Room, slug=booking_data["room"])
    rrule.organization = get_object_or_404(
        Organization, slug=booking_data["organization"]
    )
    rrule.status = rrule.organization.get_booking_status(rrule.room)
    rrule.start_time = datetime.strptime(booking_data["start_time"], "%H:%M:%S").time()  # noqa: DTZ007
    rrule.end_time = datetime.strptime(booking_data["end_time"], "%H:%M:%S").time()  # noqa: DTZ007
    rrule.rrule = booking_data.get("rrule_string", "")
    rrule.first_occurrence_date = next(iter(rrulestr(rrule.rrule)))
    rrule.differing_billing_address = booking_data["differing_billing_address"]
    rrule.compensation = None
    rrule.total_amount_per_occurrence = None
    if booking_data["compensation"]:
        rrule.compensation = get_object_or_404(
            Compensation, id=booking_data["compensation"]
        )
        if rrule.compensation.hourly_rate is not None:
            duration_hours = (timespan[1] - timespan[0]).total_seconds() / 3600
            rrule.total_amount_per_occurrence = (
                duration_hours * rrule.compensation.hourly_rate
            )

    if "COUNT" not in rrule.rrule and "UNTIL" not in rrule.rrule:
        rrule.last_occurrence_date = None
    else:
        rrule.last_occurrence_date = list(rrulestr(rrule.rrule))[-1]

    # Generate occurrences
    max_booking_date = timezone.now().date() + timedelta(days=max_future_booking_date)
    max_booking_datetime = make_aware(
        datetime.combine(max_booking_date, rrule.end_time)
    ).astimezone(UTC)
    bookings = generate_bookings(
        rrule, rrule.first_occurrence_date, max_booking_datetime
    )

    # Determine if room is at least once bookable
    bookable = any(booking.status != BookingStatus.UNAVAILABLE for booking in bookings)
    return bookings, message, rrule, bookable


def save_rrule(user, bookings, rrule):
    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied
    if user.is_staff:
        rrule.status = BookingStatus.CONFIRMED
    rrule.save()
    for booking in bookings:
        booking.save()

    async_task(
        "roomsharing.organizations.mails.manager_new_recurrence",
        rrule,
        task_name="manager-new-recurrence",
    )

    return bookings, rrule


def cancel_rrule_bookings(user, rrule_uuid):
    rrule = get_object_or_404(RecurrenceRule, uuid=rrule_uuid)
    bookings = get_list_or_404(Booking, recurrence_rule=rrule)

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    rrule.status = BookingStatus.CANCELLED
    rrule.save()

    for booking in bookings:
        if booking.is_cancelable():
            with set_actor(user):
                booking.status = BookingStatus.CANCELLED
                booking.save()

    return rrule


def get_rrules_list(user):
    organizations = organizations_with_confirmed_bookingpermission(user)
    return RecurrenceRule.objects.filter(
        booking_of_recurrencerule__organization__in=organizations
    ).distinct()


def get_rrule_bookings(user, rrule_slug):
    rrule = get_object_or_404(RecurrenceRule, slug=rrule_slug)
    bookings = get_list_or_404(Booking, recurrence_rule=rrule)

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    is_cancelable = rrule.is_cancelable()
    return rrule, bookings, is_cancelable


def manager_filter_rrules_list(organization, show_past_rrules, status):
    organizations = Organization.objects.all()
    rrules = RecurrenceRule.objects.all().distinct()
    if not show_past_rrules:
        rrules = rrules.filter(
            Q(last_occurrence_date__gte=timezone.now())
            | Q(last_occurrence_date__isnull=True)
        )
    if organization != "all":
        rrules = rrules.filter(
            booking_of_recurrencerule__organization__slug=organization
        )
    if status != "all":
        rrules = rrules.filter(status=status)
    rrules = rrules.order_by("created")

    return rrules, organizations


def manager_cancel_rrule(user, rrule_uuid):
    rrule = get_object_or_404(RecurrenceRule, uuid=rrule_uuid)
    bookings = get_list_or_404(Booking, recurrence_rule=rrule)
    rrule.status = BookingStatus.CANCELLED
    rrule.save()

    for booking in bookings:
        if booking.is_cancelable():
            with set_actor(user):
                booking.status = BookingStatus.CANCELLED
                booking.save()

    async_task(
        "roomsharing.organizations.mails.recurrence_cancellation_email",
        rrule,
        task_name="recurrence-cancellation-email",
    )
    return rrule


def extend_recurrences():
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

    rrules = RecurrenceRule.objects.filter(
        Q(last_occurrence_date=None)
        | Q(last_occurrence_date__gte=start_new_bookings_at)
    ).filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
    rrules = rrules.order_by("created")
    new_bookings = []
    for current_rrule in rrules:
        # generate bookings that are after max booking date and before target date
        bookings = generate_bookings(
            current_rrule, start_new_bookings_at, end_new_bookings_at
        )
        for current_booking in bookings:
            # Determine if the current booking stems from the same rrule and thus
            # should not be saved
            is_same_rrule_booking = (
                current_booking.status == BookingStatus.UNAVAILABLE
                and Booking.objects.filter(room=current_rrule.room)
                .filter(timespan__overlap=current_booking.timespan)
                .filter(recurrence_rule=current_rrule)
                .exists()
            )
            if not is_same_rrule_booking:
                current_booking.save()
                new_bookings.append(current_booking)

    return new_bookings


def generate_bookings(rrule, start_datetime, end_datetime):
    last_occurrence_before_end_datetime = rrulestr(rrule.rrule).before(
        end_datetime, inc=True
    )
    occurrences = list(
        rrulestr(rrule.rrule).between(
            start_datetime, last_occurrence_before_end_datetime, inc=True
        )
    )

    # Helper function to create a booking
    def create_rrule_booking(occurrence):
        b_start_datetime = timezone.make_aware(
            datetime.combine(occurrence, rrule.start_time)
        )
        b_end_datetime = timezone.make_aware(
            datetime.combine(occurrence, rrule.end_time)
        )
        timespan = (b_start_datetime, b_end_datetime)
        booking = Booking(
            title=rrule.title,
            user=rrule.user,
            room=rrule.room,
            timespan=timespan,
            organization=rrule.organization,
            status=rrule.status,
            start_date=occurrence.date(),
            start_time=rrule.start_time,
            end_time=rrule.end_time,
            compensation=rrule.compensation,
            total_amount=rrule.total_amount_per_occurrence,
            recurrence_rule=rrule,
            auto_generated_on=timezone.now(),
            differing_billing_address=rrule.differing_billing_address,
        )
        if booking.room.is_booked(booking.timespan):
            booking.status = BookingStatus.UNAVAILABLE
        return booking

    # Create bookings in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        return list(executor.map(create_rrule_booking, occurrences))
