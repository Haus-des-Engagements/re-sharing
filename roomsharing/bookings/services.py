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
from django.shortcuts import get_list_or_404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_q.models import Schedule
from django_q.tasks import async_task
from django_q.tasks import schedule

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
    startdate = rrule_data["startdate"]

    if rrule_ends == "AFTER_TIMES":
        count = rrule_ends_count
        rrule_enddate = None
    else:
        count = None
        rrule_enddate = rrule_ends_enddate

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
        dtstart=startdate,
        bysetpos=None,
        until=rrule_enddate,
        count=count,
    )
    return str(recurrence_pattern)


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
    if booking.status == BookingStatus.CONFIRMED and (
        booking.timespan.lower - timedelta(days=7) > timezone.now()
    ):
        schedule(
            "roomsharing.bookings.tasks.booking_reminder_email",
            booking_slug=booking.slug,
            task_name="booking-reminder-email",
            schedule_type=Schedule.ONCE,
            next_run=booking.timespan.lower - timedelta(days=7),
        )

    return booking


def generate_recurrence(booking_data):
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

    bookings = []
    occurrences = list(rrulestr(rrule_string))
    starttime = timespan[0].time()
    endtime = timespan[1].time()
    rrule_total_amount = 0
    for occurrence in occurrences:
        start_datetime = timezone.make_aware(datetime.combine(occurrence, starttime))
        end_datetime = timezone.make_aware(datetime.combine(occurrence, endtime))
        timespan = (start_datetime, end_datetime)
        compensation = None
        total_amount = None
        if booking_data["compensation"] != "":
            compensation = get_object_or_404(
                Compensation, id=booking_data["compensation"]
            )
            if compensation.hourly_rate is not None:
                total_amount = (
                    (end_datetime - start_datetime).total_seconds()
                    / 3600
                    * compensation.hourly_rate
                )
                rrule_total_amount = rrule_total_amount + total_amount

        booking_details = {
            "user": user,
            "title": title,
            "room": room,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "organization": organization,
            "status": status,
            "timespan": timespan,
            "start_date": occurrence.date(),
            "start_time": start_time,
            "end_time": end_time,
            "compensation": compensation,
            "total_amount": total_amount,
        }

        rrule = RecurrenceRule()
        rrule.rrule = rrule_string
        rrule.start_time = starttime
        rrule.end_time = endtime
        rrule.first_occurrence_date = next(iter(rrulestr(rrule_string)))
        rrule.last_occurrence_date = list(rrulestr(rrule_string))[-1]
        rrule.excepted_dates = []

        bookings.append(
            create_booking(booking_details, room_booked=room.is_booked(timespan))
        )
    bookable = len([booking for booking in bookings if booking.room_booked]) < len(
        bookings
    )

    return bookings, message, rrule, bookable, rrule_total_amount


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
    )
    booking.room_booked = kwargs.get("room_booked") or None
    booking.rrule = kwargs.get("rrule") or None
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
    if endtime:
        initial_data["endtime"] = endtime
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


def filter_bookings_list(
    organization, show_past_bookings, status, user, hide_recurring_bookings
):
    organizations = organizations_with_confirmed_bookingpermission(user)
    bookings = Booking.objects.filter(organization__in=organizations)
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if hide_recurring_bookings:
        bookings = bookings.filter(recurrence_rule__isnull=True)

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
    }
    rrule_string = None
    if form.cleaned_data["rrule_repetitions"] != "NO_REPETITIONS":
        rrule_string = create_rrule_string(form.cleaned_data)
        booking_data["rrule_string"] = rrule_string

    return booking_data, rrule_string


def manager_filter_bookings_list(
    organization, show_past_bookings, status, hide_recurring_bookings
):
    organizations = Organization.objects.all()
    bookings = Booking.objects.all()
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if hide_recurring_bookings:
        bookings = bookings.filter(recurrence_rule__isnull=True)

    bookings.order_by("created")

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
        schedule(
            "roomsharing.bookings.tasks.booking_reminder_email",
            booking_slug=booking.slug,
            task_name="booking-reminder-email",
            schedule_type=Schedule.ONCE,
            next_run=booking.timespan.lower - timedelta(days=7),
        )

        return booking

    raise InvalidBookingOperationError
