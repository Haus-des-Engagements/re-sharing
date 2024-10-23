# tasks.py

from django.contrib.sites.models import Site
from django.core.mail import EmailMessage
from django.core.mail import send_mail
from django.utils import timezone
from icalendar import Calendar
from icalendar import Event

from roomsharing.utils.models import BookingStatus


def booking_confirmation_email(booking):
    domain = Site.objects.get_current().domain
    cal = Calendar()
    event = Event()

    event.add("uid", booking.uuid)
    event.add("summary", booking.title)
    event.add("dtstart", booking.timespan.lower)
    event.add("dtend", booking.timespan.upper)
    event.add("dtstamp", timezone.now())
    event.add("location", booking.room.name)
    event["description"] = (
        f"Find all related information (access(ability), door code) and actions "
        f"(cancel) here: {domain}{booking.get_absolute_url()}"
    )
    cal.add_component(event)

    # Create an ICS file
    ical_content = cal.to_ical()
    ical_filename = f"booking_{booking.slug}.ics"
    email = EmailMessage(
        "Booking Confirmed",
        f"Your booking {booking.title} has been confirmed. You can see and "
        f"change it here: {booking.get_absolute_url()}",
        "raum.app@haus-des-engagements.de",
        [booking.user.email],
    )
    email.attach(ical_filename, ical_content, "text/calendar")
    email.send(fail_silently=False)


def booking_reminder_email(booking_slug):
    from roomsharing.bookings.models import Booking

    booking = Booking.objects.get(slug=booking_slug)
    if booking.status == BookingStatus.CONFIRMED:
        send_mail(
            "Booking Reminder",
            f'Your booking "{booking.title}"is in 3 days. You can see and change it '
            f"here: {booking.get_absolute_url()} . "
            " Please cancel the booking "
            " if you no longer need the rooms so that others can use it."
            " Best regards,"
            " your friendly room bot.",
            "raum.app@haus-des-engagements.de",
            [booking.user.email],
        )


def cancel_booking_email(booking):
    if booking.status == BookingStatus.CANCELLED:
        send_mail(
            "Booking cancelled",
            f'Your booking "{booking.title}" has been cancelled. You can see '
            f"and change it here: {booking.get_absolute_url()}."
            "Best regards,"
            "your friendly room bot.",
            "raum.app@haus-des-engagements.de",
            [booking.user.email],
        )


def recurrence_confirmation_email(rrule):
    send_mail(
        "Recurrence Confirmed",
        f"Your recurring bookings {rrule.get_first_booking.title} have "
        f"been confirmed. You can see and change it here: {rrule.get_absolute_url()}",
        "raum.app@haus-des-engagements.de",
        [rrule.user.email],
        fail_silently=False,
    )
