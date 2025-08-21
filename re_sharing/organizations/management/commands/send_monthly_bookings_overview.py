from django.core.management.base import BaseCommand

from re_sharing.organizations.mails import send_monthly_bookings_overview


class Command(BaseCommand):
    help = "Send monthly bookings overview"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=1,
            help="For how many months ahead to send booking overview (default is 1).",
        )

    def handle(self, *args, **kwargs):
        months = kwargs["months"]
        result = send_monthly_bookings_overview(months=months)
        # Optionally, log the result
        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders send for {result['next_month_start']} for  "
                f"{result['organizations_processed']} organizations: "
                f"{result['organizations_list']}"
            )
        )
