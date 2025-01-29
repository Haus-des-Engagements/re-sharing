from django.core.management.base import BaseCommand

from re_sharing.organizations.mails import send_booking_reminder_emails


class Command(BaseCommand):
    help = "Extend booking series"

    def handle(self, *args, **kwargs):
        # Call your function here
        bookings = send_booking_reminder_emails()
        # Optionally, log the result
        self.stdout.write(self.style.SUCCESS(f"Reminder send for: {bookings}"))
