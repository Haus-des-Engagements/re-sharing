# tasks.py
from django.core.mail import send_mail

from roomsharing.utils.models import BookingStatus


def booking_confirmation_email(booking):
    send_mail(
        "Booking Confirmed",
        f"Your booking {booking.title} has been confirmed. You can see and change it "
        f"here: {booking.get_absolute_url()}",
        "raum.app@haus-des-engagements.de",
        [booking.user.email],
        fail_silently=False,
    )


def booking_reminder_email(booking_slug):
    from roomsharing.bookings.models import Booking

    booking = Booking.objects.get(slug=booking_slug)
    if booking.status == BookingStatus.CONFIRMED:
        send_mail(
            "Booking Reminder",
            f'Your booking "{booking.title}"is in 3 days. You can see and change it '
            f"here: {booking.get_absolute_url()} . "
            " Please cancel the booking "
            " if you no longer need the rooms so that others can use it.",
            " Best regards,"
            " your friendly room bot."
            "raum.app@haus-des-engagements.de",
            [booking.user.email],
        )
