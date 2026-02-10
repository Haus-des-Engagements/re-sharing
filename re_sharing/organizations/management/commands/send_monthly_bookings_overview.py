from collections import defaultdict

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.organizations.mails import send_monthly_overview_email
from re_sharing.organizations.models import Organization
from re_sharing.utils.models import BookingStatus


class Command(BaseCommand):
    help = "Enqueue monthly bookings overview emails as background tasks"

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

        # Calculate the target month
        next_month = timezone.now() + relativedelta(months=+months)
        next_month_start = next_month.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        # Get bookings for organizations with bulk access codes
        bookings = Booking.objects.filter(
            status=BookingStatus.CONFIRMED, organization__monthly_bulk_access_codes=True
        )

        # Filter by specific organizations if provided
        if organizations is not None:
            bookings = bookings.filter(organization__in=organizations)

        bookings = bookings.filter(
            timespan__startswith__gte=next_month_start,
            timespan__startswith__lt=next_month_start + relativedelta(months=1),
        )

        # Group bookings by organization
        bookings_by_org = defaultdict(list)
        for booking in bookings:
            bookings_by_org[booking.organization].append(booking.id)

        # Enqueue a task for each organization
        enqueued_count = 0
        organization_names = []
        for organization, booking_ids in bookings_by_org.items():
            send_monthly_overview_email.enqueue(
                organization.id,
                booking_ids,
                next_month.isoformat(),
            )
            organization_names.append(organization.name)
            enqueued_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Enqueued {enqueued_count} monthly overview email tasks "
                f"for {next_month_start.date()}: {organization_names}"
            )
        )
