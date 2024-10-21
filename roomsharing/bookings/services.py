import concurrent
import re
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from http import HTTPStatus

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
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_list_or_404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_q.tasks import async_task

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingMessage
from roomsharing.bookings.models import RecurrenceRule
from roomsharing.organizations.models import Organization
from roomsharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from roomsharing.organizations.services import user_has_bookingpermission
from roomsharing.rooms.models import Compensation
from roomsharing.rooms.models import Room
from roomsharing.rooms.services import get_access_code
from roomsharing.users.models import User
from roomsharing.utils.models import BookingStatus


class InvalidBookingOperationError(Exception):
    def __init__(self):
        self.message = "You cannot perform this action."
        self.status_code = HTTPStatus.BAD_REQUEST


def show_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    activity_stream = get_booking_activity_stream(booking)

    access_code = get_access_code(
        booking.room.slug, booking.organization.slug, booking.timespan.lower
    )

    if access_code and booking.status in [
        BookingStatus.PENDING,
        BookingStatus.CANCELLED,
    ]:
        access_code = _("only shown when confirmed")
    elif access_code and booking.status == BookingStatus.CONFIRMED:
        access_code = access_code.code
    else:
        access_code = "not necessary"

    return booking, activity_stream, access_code


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


def generate_single_booking(booking_data):
    message = booking_data["message"]
    timespan = (
        isoparse(booking_data["timespan"][0]),
        isoparse(booking_data["timespan"][1]),
    )
    organization = get_object_or_404(Organization, slug=booking_data["organization"])
    room = get_object_or_404(Room, slug=booking_data["room"])

    start_datetime = timespan[0]
    end_datetime = timespan[1]
    compensation = None
    total_amount = None
    if booking_data["compensation"] != "":
        compensation = get_object_or_404(Compensation, id=booking_data["compensation"])
        if compensation.hourly_rate is not None:
            total_amount = (
                (end_datetime - start_datetime).total_seconds()
                / 3600
                * compensation.hourly_rate
            )

    booking_details = {
        "user": get_object_or_404(User, slug=booking_data["user"]),
        "title": booking_data["title"],
        "room": room,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "organization": organization,
        "status": organization.default_booking_status(room),
        "timespan": timespan,
        "start_date": booking_data["start_date"],
        "start_time": booking_data["start_time"],
        "end_time": booking_data["end_time"],
        "compensation": compensation,
        "total_amount": total_amount,
        "differing_billing_address": booking_data["differing_billing_address"],
    }
    booking = create_booking(booking_details)
    return booking, message


def save_booking(user, booking, message):
    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    booking.save()
    if message:
        save_bookingmessage(booking, message, user)

    # re-retrieve booking object, to be able to call timespan.lower
    booking.refresh_from_db()
    if booking.status == BookingStatus.CONFIRMED and not booking.recurrence_rule:
        async_task(
            "roomsharing.bookings.tasks.booking_confirmation_email",
            booking,
            task_name="booking-confirmation-email",
        )

    return booking


def generate_occurrences(booking_data):
    message = booking_data["message"]
    timespan = (
        isoparse(booking_data["timespan"][0]),
        isoparse(booking_data["timespan"][1]),
    )
    user = get_object_or_404(User, slug=booking_data["user"])
    title = booking_data["title"]
    room = get_object_or_404(Room, slug=booking_data["room"])
    organization = get_object_or_404(Organization, slug=booking_data["organization"])
    status = organization.default_booking_status(room)
    start_time = booking_data["start_time"]
    end_time = booking_data["end_time"]
    rrule_string = booking_data.get("rrule_string", "")
    limited_rrule_string = rrule_string
    # Limit the recurrence rule if needed
    if "COUNT" not in rrule_string and "UNTIL" not in rrule_string:
        future_date = timezone.now() + timedelta(days=730)
        formatted_date = future_date.strftime("%Y%m%dT%H%M%S")
        limited_rrule_string = rrule_string + f";UNTIL={formatted_date}Z"

    # Generate occurrences
    occurrences = list(rrulestr(limited_rrule_string))
    starttime_naive = timespan[0].time()
    endtime_naive = timespan[1].time()
    # Calculate the total amount if compensation is provided
    compensation = None
    total_amount = None
    if booking_data["compensation"]:
        compensation = get_object_or_404(Compensation, id=booking_data["compensation"])
        if compensation.hourly_rate is not None:
            duration_hours = (timespan[1] - timespan[0]).total_seconds() / 3600
            total_amount = duration_hours * compensation.hourly_rate

    # Helper function to create a booking
    def create_booking(occurrence):
        start_datetime = timezone.make_aware(
            datetime.combine(occurrence, starttime_naive)
        )
        end_datetime = timezone.make_aware(datetime.combine(occurrence, endtime_naive))
        timespan = (start_datetime, end_datetime)
        booking = Booking(
            user=user,
            title=title,
            room=room,
            timespan=timespan,
            organization=organization,
            status=status,
            start_date=occurrence.date(),
            start_time=start_time,
            end_time=end_time,
            compensation=compensation,
            total_amount=total_amount,
            differing_billing_address=booking_data["differing_billing_address"],
        )
        booking.room_booked = room.is_booked(timespan)
        return booking

    # Create bookings in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        bookings = list(executor.map(create_booking, occurrences))

    # Create recurrence rule
    rrule = RecurrenceRule()
    rrule.rrule = rrule_string
    rrule.start_time = start_time
    rrule.end_time = end_time
    rrule.first_occurrence_date = next(iter(rrulestr(rrule_string)))
    if "COUNT" not in rrule_string and "UNTIL" not in rrule_string:
        rrule.last_occurrence_date = None
    else:
        rrule.last_occurrence_date = list(rrulestr(rrule_string))[-1]
    rrule.excepted_dates = []

    # Determine if room is bookable
    bookable = any(not booking.room_booked for booking in bookings)

    return bookings, message, rrule, bookable


def create_booking(booking_details, **kwargs):
    booking = Booking(
        user=booking_details["user"],
        title=booking_details["title"],
        room=booking_details["room"],
        timespan=booking_details["timespan"],
        organization=booking_details["organization"],
        status=booking_details["status"],
        start_date=booking_details["start_date"],
        start_time=booking_details["start_time"],
        end_time=booking_details["end_time"],
        compensation=booking_details["compensation"],
        total_amount=booking_details["total_amount"],
        differing_billing_address=booking_details["differing_billing_address"],
    )
    booking.room_booked = kwargs.get("room_booked") or None
    return booking


def save_bookingmessage(booking, message, user):
    booking_message = BookingMessage(
        booking=booking,
        text=message,
        user=user,
    )
    booking_message.save()
    return booking_message


def create_bookingmessage(booking_slug, form, user):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    if form.is_valid():
        message = form.cleaned_data["text"]
        return save_bookingmessage(booking, message, user)

    raise InvalidBookingOperationError


def save_recurrence(user, bookings, message, rrule):
    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied
    excepted_dates = []
    # save bookings or - if room not available - add it to excepted dates
    if user.is_staff:
        rrule.status = BookingStatus.CONFIRMED
    rrule.save()
    for booking in bookings:
        if booking.room_booked:
            excepted_dates.append(booking.start_date)
        else:
            booking.recurrence_rule = rrule
            save_booking(user, booking, message)

    rrule.excepted_dates = excepted_dates
    rrule.save()

    return bookings, rrule


def set_initial_booking_data(endtime, startdate, starttime, room):
    initial_data = {}
    if startdate:
        initial_data["startdate"] = startdate
    else:
        initial_data["startdate"] = datetime.strftime(timezone.now().date(), "%Y-%m-%d")
    if starttime:
        initial_data["starttime"] = starttime
        starttime = datetime.strptime(starttime, "%H:%M").astimezone(
            timezone.get_current_timezone()
        )
    else:
        starttime = timezone.localtime(timezone.now()) + timedelta(hours=1)
        initial_data["starttime"] = datetime.strftime(starttime, "%H:00")
    if endtime:
        initial_data["endtime"] = endtime
    else:
        endtime = starttime + timedelta(hours=1)
        initial_data["endtime"] = datetime.strftime(endtime, "%H:00")
    if room:
        initial_data["room"] = get_object_or_404(Room, slug=room)
    return initial_data


def cancel_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    if booking.is_cancelable():
        with set_actor(user):
            booking.status = BookingStatus.CANCELLED
            booking.save()

        return booking

    raise InvalidBookingOperationError


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


def get_booking_activity_stream(booking):
    activity_stream = []
    booking_logs = booking.history.filter(changes__has_key="status").exclude(
        changes__status__contains="None"
    )
    for log_entry in booking_logs:
        status_integer_old = int(log_entry.changes["status"][0])
        status_text_old = dict(BookingStatus.choices).get(status_integer_old)

        status_integer_new = int(log_entry.changes["status"][1])
        status_text_new = dict(BookingStatus.choices).get(status_integer_new)
        status_change_dict = {
            "date": log_entry.timestamp,
            "type": "status_change",
            "old_status": [status_integer_old, status_text_old],
            "new_status": [status_integer_new, status_text_new],
            "user": get_object_or_404(User, id=log_entry.actor_id),
        }
        activity_stream.append(status_change_dict)
    messages = BookingMessage.objects.filter(booking=booking)
    for message in messages:
        message_dict = {
            "date": message.created,
            "type": "message",
            "text": message.text,
            "user": message.user,
        }
        activity_stream.append(message_dict)
    return sorted(activity_stream, key=lambda x: x["date"], reverse=True)


def filter_bookings_list(  # noqa: PLR0913
    organization, show_past_bookings, status, user, hide_recurring_bookings, page_number
):
    organizations = organizations_with_confirmed_bookingpermission(user)
    related_fields = [
        "organization",
        "room__compensations_of_room",
        "user",
        "recurrence_rule",
    ]
    bookings = Booking.objects.filter(organization__in=organizations).prefetch_related(
        *related_fields
    )
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if hide_recurring_bookings:
        bookings = bookings.filter(recurrence_rule__isnull=True)

    paginator = Paginator(bookings, 100)
    page_objects = paginator.get_page(page_number)
    bookings = page_objects

    return bookings, organizations


def get_recurrences_list(user):
    organizations = organizations_with_confirmed_bookingpermission(user)
    return RecurrenceRule.objects.filter(
        booking_of_recurrencerule__organization__in=organizations
    ).distinct()


def get_occurrences(user, recurrence_uuid):
    rrule = get_object_or_404(RecurrenceRule, uuid=recurrence_uuid)
    bookings = get_list_or_404(Booking, recurrence_rule=rrule)

    if not user_has_bookingpermission(user, bookings[0]):
        raise PermissionDenied

    is_cancelable = rrule.is_cancelable()

    return rrule, bookings, is_cancelable


def confirm_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    if booking.is_confirmable():
        with set_actor(user):
            booking.status = BookingStatus.CONFIRMED
            booking.save()
            return booking

    raise InvalidBookingOperationError


def create_booking_data(user, form):
    if isinstance(form.cleaned_data["timespan"], tuple):
        timespan_start, timespan_end = form.cleaned_data["timespan"]
        timespan = (timespan_start.isoformat(), timespan_end.isoformat())

    booking_data = {
        "title": form.cleaned_data["title"],
        "room": form.cleaned_data["room"].slug,
        "timespan": timespan,
        "organization": form.cleaned_data["organization"].slug,
        "message": form.cleaned_data["message"],
        "start_date": form.cleaned_data["startdate"].isoformat(),
        "start_time": form.cleaned_data["starttime"].isoformat(),
        "end_time": form.cleaned_data["endtime"].isoformat(),
        "user": user.slug,
        "compensation": form.cleaned_data["compensation"].id,
        "start_datetime": form.cleaned_data["start_datetime"].isoformat(),
        "differing_billing_address": form.cleaned_data["differing_billing_address"],
    }
    rrule_string = None
    if form.cleaned_data["rrule_repetitions"] != "NO_REPETITIONS":
        rrule_string = create_rrule_string(form.cleaned_data)
        booking_data["rrule_string"] = rrule_string

    return booking_data, rrule_string


def manager_filter_bookings_list(
    organization, show_past_bookings, status, show_recurring_bookings
):
    organizations = Organization.objects.all()
    related_fields = [
        "organization",
        "room__compensations_of_room",
        "user",
        "recurrence_rule",
    ]
    bookings = Booking.objects.prefetch_related(*related_fields)
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if not show_recurring_bookings:
        bookings = bookings.filter(recurrence_rule__isnull=True)

    bookings = bookings.order_by("created")

    return bookings, organizations


def manager_cancel_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if booking.is_cancelable():
        with set_actor(user):
            booking.status = BookingStatus.CANCELLED
            booking.save()
        async_task(
            "roomsharing.bookings.tasks.cancel_booking_email",
            booking,
            task_name="cancel-booking-email",
        )

        return booking

    raise InvalidBookingOperationError


def manager_confirm_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)
    if booking.is_confirmable():
        with set_actor(user):
            booking.status = BookingStatus.CONFIRMED
            booking.save()
        async_task(
            "roomsharing.bookings.tasks.booking_confirmation_email",
            booking,
            task_name="booking-confirmation-email",
        )

        return booking

    raise InvalidBookingOperationError


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


def manager_confirm_rrule(user, rrule_uuid):
    rrule = get_object_or_404(RecurrenceRule, uuid=rrule_uuid)
    bookings = get_list_or_404(Booking, recurrence_rule=rrule)
    rrule.status = BookingStatus.CONFIRMED
    rrule.save()
    for booking in bookings:
        if booking.is_confirmable():
            with set_actor(user):
                booking.status = BookingStatus.CONFIRMED
                booking.save()
    async_task(
        "roomsharing.bookings.tasks.recurrence_confirmation_email",
        rrule,
        task_name="recurrence-confirmation-email",
    )

    return rrule


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
        "roomsharing.bookings.tasks.recurrence_cancellation_email",
        rrule,
        task_name="recurrence-cancellation-email",
    )
    return rrule


def extend_recurrences():
    max_booking_date = timezone.now() + timedelta(days=729)
    rrules = RecurrenceRule.objects.filter(
        Q(last_occurrence_date=None) | Q(last_occurrence_date__gt=max_booking_date)
    ).filter(status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
    rrules = rrules.order_by("created")
    target_date = timezone.now() + timedelta(days=732)

    for single_rrule in rrules:
        # find occurrences that are after max booking date and before target date
        occurrences = list(
            rrulestr(single_rrule.rrule).between(
                max_booking_date, target_date, inc=True
            )
        )
        # get one existing booking
        proto_booking = single_rrule.get_first_booking()
        for occurrence in occurrences:
            start_datetime = timezone.make_aware(
                datetime.combine(occurrence, proto_booking.start_time)
            )
            end_datetime = timezone.make_aware(
                datetime.combine(occurrence, proto_booking.end_time)
            )
            timespan = (start_datetime, end_datetime)
            booking = Booking(
                user=proto_booking.user,
                title=proto_booking.title,
                room=proto_booking.room,
                timespan=timespan,
                organization=proto_booking.organization,
                status=single_rrule.status,
                start_date=occurrence.date(),
                start_time=proto_booking.start_time,
                end_time=proto_booking.end_time,
                compensation=proto_booking.compensation,
                total_amount=proto_booking.total_amount,
                recurrence_rule=single_rrule,
                auto_generated_on=timezone.now(),
            )
            if not booking.room.is_booked(timespan):
                booking.save()


def collect_booking_reminder_mails():
    bookings = Booking.objects.filter(status=BookingStatus.CONFIRMED)
    dt_in_5_days = timezone.now() + timedelta(days=5)
    dt_in_5_days = dt_in_5_days.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_in_6_days = dt_in_5_days + timedelta(days=1)
    bookings = bookings.filter(timespan__startswith__gte=dt_in_5_days)
    bookings = bookings.filter(timespan__startswith__lt=dt_in_6_days)
    processed_slugs = []

    for booking in bookings:
        async_task(
            "roomsharing.bookings.tasks.booking_reminder_email",
            booking_slug=booking.slug,
            task_name="booking-reminder-email",
        )
        processed_slugs.append(booking.slug)
    return processed_slugs
