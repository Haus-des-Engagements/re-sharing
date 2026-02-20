from django.core.management.base import BaseCommand

from re_sharing.resources.models import Access
from re_sharing.resources.services_nuki import sync_all_smartlock_codes


class Command(BaseCommand):
    help = "Enqueue NUKI smartlock code sync task for all smartlocks (today's bookings)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be synced without actually enqueueing tasks",
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs["dry_run"]

        smartlock_count = (
            Access.objects.exclude(smartlock_id="")
            .values_list("smartlock_id", flat=True)
            .distinct()
            .count()
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no task will be enqueued"))
            self.stdout.write(
                f"  Would sync {smartlock_count} smartlock(s) in a single task"
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Would enqueue 1 task to sync {smartlock_count} smartlock(s)"
                )
            )
        else:
            sync_all_smartlock_codes.enqueue()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enqueued 1 task to sync {smartlock_count} smartlock(s)"
                )
            )
