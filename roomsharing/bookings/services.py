from datetime import datetime

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
from django.shortcuts import get_object_or_404
from django.utils import timezone

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingMessage
from roomsharing.bookings.models import RecurrenceRule
from roomsharing.bookings.selectors import get_default_booking_status
from roomsharing.bookings.selectors import room_is_booked
from roomsharing.organizations.models import Organization
from roomsharing.rooms.models import Room
from roomsharing.utils.models import BookingStatus


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


def generate_bookings(request):
    booking_data = request.session["booking_data"]
    message = booking_data["message"]
    timespan = (
        isoparse(booking_data["timespan"][0]),
        isoparse(booking_data["timespan"][1]),
    )
    user = request.user
    title = booking_data["title"]
    room = get_object_or_404(Room, slug=booking_data["room"])
    organization = get_object_or_404(Organization, slug=booking_data["organization"])
    status = get_default_booking_status(organization, room)
    start_time = booking_data["start_time"]
    end_time = booking_data["end_time"]
    start_date = booking_data["start_date"]
    rrule_string = booking_data.get("rrule_string", "")

    bookings = []
    if rrule_string:
        occurrences = list(rrulestr(rrule_string))
        starttime = timespan[0].time()
        endtime = timespan[1].time()
        for occurrence in occurrences:
            start_datetime = timezone.make_aware(
                datetime.combine(occurrence, starttime)
            )
            end_datetime = timezone.make_aware(datetime.combine(occurrence, endtime))
            booking_details = {
                "user": user,
                "title": title,
                "room": room,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "organization": organization,
                "status": status,
                "timespan": (start_datetime, end_datetime),
                "start_date": occurrence.date(),
                "start_time": start_time,
                "end_time": end_time,
            }
            room_booked = room_is_booked(room, start_datetime, end_datetime)
            rrule = rrule_string

            bookings.append(
                create_booking(booking_details, room_booked=room_booked, rrule=rrule)
            )
    else:
        start_datetime = timespan[0]
        end_datetime = timespan[1]
        booking_details = {
            "user": user,
            "title": title,
            "room": room,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "organization": organization,
            "status": status,
            "timespan": timespan,
            "start_date": start_date,
            "start_time": start_time,
            "end_time": end_time,
        }
        room_booked = room_is_booked(room, start_datetime, end_datetime)
        rrule = rrule_string

        bookings.append(
            create_booking(booking_details, room_booked=room_booked, rrule=rrule)
        )

    return bookings, message, rrule_string


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
    )
    booking.room_booked = kwargs.get("room_booked")
    booking.rrule = kwargs.get("rrule")
    return booking


def save_bookingmessage(booking, message, user):
    booking_message = BookingMessage(
        booking=booking,
        text=message,
        user=user,
    )
    booking_message.save()
    return booking_message


def save_bookings(bookings, message, rrule_string):
    excepted_dates = []
    for booking in bookings:
        if booking.room_booked:
            excepted_dates.append(booking.start_date)
        else:
            booking.save()
            if message:
                save_bookingmessage(booking, message, booking.user)
    if bookings[0].rrule and len(excepted_dates) != len(bookings):
        rrule = RecurrenceRule()
        rrule.rrule = bookings[0].rrule
        rrule.start_time = bookings[0].start_time
        rrule.end_time = bookings[0].end_time
        rrule.first_occurrence_date = next(iter(rrulestr(rrule_string)))
        rrule.last_occurrence_date = list(rrulestr(rrule_string))[-1]
        rrule.excepted_dates = excepted_dates
        rrule.room = bookings[0].room
        rrule.save()
        for booking in bookings:
            if not booking.room_booked:
                booking.recurrence_rule = rrule
                booking.save()


def set_initial_booking_data(endtime, startdate, starttime):
    initial_data = {}
    if startdate:
        initial_data["startdate"] = startdate
    else:
        initial_data["startdate"] = datetime.strftime(timezone.now().date(), "%Y-%m-%d")
    if starttime:
        initial_data["starttime"] = starttime
    if endtime:
        initial_data["endtime"] = endtime
    return initial_data


def cancel_booking(booking):
    booking.status = BookingStatus.CANCELLED
    booking.save()
    return booking
