from django.core.management.base import BaseCommand

from re_sharing.organizations.mails import send_booking_reminder_emails


class Command(BaseCommand):
    help = "Send booking reminder emails"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=5,
            help="Number of days ahead to send booking reminders (default is 5 days).",
        )

    def handle(self, *args, **kwargs):
        days = kwargs["days"]
        reminded_bookings, day = send_booking_reminder_emails(days=days)
        # Optionally, log the result
        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders send for {len(reminded_bookings)} "
                f"bookings (on {day}): {reminded_bookings}"
            )
        )
