from django.core.management.base import BaseCommand

from re_sharing.organizations.mails import send_monthly_bookings_overview
from re_sharing.organizations.models import Organization


class Command(BaseCommand):
    help = "Send monthly bookings overview"

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=1,
            help="For how many months ahead to send booking overview (default is 1).",
        )
        parser.add_argument(
            "--organizations",
            nargs="*",
            help="Organization slugs to send overview for (if not provided, all "
            "eligible organizations will be processed).",
        )

    def handle(self, *args, **kwargs):
        months = kwargs["months"]
        organization_slugs = kwargs["organizations"]

        organizations = None
        if organization_slugs:
            organizations = Organization.objects.filter(slug__in=organization_slugs)
            if organizations.count() != len(organization_slugs):
                found_slugs = set(organizations.values_list("slug", flat=True))
                missing_slugs = set(organization_slugs) - found_slugs
                self.stdout.write(
                    self.style.WARNING(
                        f"Warning: Organizations not found: {', '.join(missing_slugs)}"
                    )
                )

        result = send_monthly_bookings_overview(
            months=months, organizations=organizations
        )
        # Optionally, log the result
        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders send for {result['next_month_start']} for  "
                f"{result['organizations_processed']} organizations: "
                f"{result['organizations_list']}"
            )
        )
