from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.organizations.mails import send_booking_reminder_email
from re_sharing.utils.models import BookingStatus


class Command(BaseCommand):
    help = "Enqueue booking reminder emails as background tasks"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=5,
            help="Number of days ahead to send booking reminders (default is 5 days).",
        )

    def handle(self, *args, **kwargs):
        days = kwargs["days"]

        # Get bookings that need reminders
        bookings = Booking.objects.filter(status=BookingStatus.CONFIRMED)
        # Exclude bookings from organizations that use the "sent bulk access codes"
        bookings = bookings.exclude(organization__monthly_bulk_access_codes=True)
        # Filter for bookings that are not part of a booking series
        # or a part of booking series where the reminder mails should be sent out
        bookings = bookings.filter(
            Q(booking_series__isnull=True) | Q(booking_series__reminder_emails=True)
        )
        dt_in_days = timezone.now() + timedelta(days=days)
        dt_in_days = dt_in_days.replace(hour=0, minute=0, second=0, microsecond=0)
        dt_in_next_day = dt_in_days + timedelta(days=1)
        bookings = bookings.filter(timespan__startswith__gte=dt_in_days)
        bookings = bookings.filter(timespan__startswith__lt=dt_in_next_day)

        # Enqueue a task for each booking
        enqueued_count = 0
        booking_slugs = []
        for booking in bookings:
            send_booking_reminder_email.enqueue(booking.id)
            booking_slugs.append(booking.slug)
            enqueued_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Enqueued {enqueued_count} reminder email tasks "
                f"for bookings on {dt_in_days.date()}: {booking_slugs}"
            )
        )
