from django.shortcuts import get_object_or_404
from django.utils import timezone

from roomsharing.organizations.models import DefaultBookingStatus
from roomsharing.users.models import User
from roomsharing.utils.models import BookingStatus

from .models import Booking
from .models import BookingMessage


def room_is_booked(room, start_datetime, end_datetime):
    return (
        Booking.objects.all()
        .filter(
            status=BookingStatus.CONFIRMED,
            room=room,
            timespan__overlap=(start_datetime, end_datetime),
        )
        .exists()
    )


def get_default_booking_status(organization, room):
    default_booking_status = DefaultBookingStatus.objects.filter(
        organization=organization, room=room
    )
    if default_booking_status.exists():
        return default_booking_status.first().status

    return BookingStatus.PENDING


def get_future_bookings(organizations):
    return Booking.objects.filter(organization__in=organizations).filter(
        timespan__endswith__gte=timezone.now()
    )


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


def filter_bookings_list(bookings, organization, show_past_bookings, status):
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if status != "all":
        bookings = bookings.filter(status__in=status)

    return bookings
