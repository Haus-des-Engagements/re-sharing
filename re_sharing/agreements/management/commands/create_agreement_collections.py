from django.core.management.base import BaseCommand
from django.utils import timezone

from re_sharing.agreements.services_collections import create_due_collections
from re_sharing.agreements.services_collections import notify_due_collections


class Command(BaseCommand):
    help = "Create fee collections within the lookahead and send pre-notifications."

    def handle(self, *args, **options):
        today = timezone.localdate()
        created = create_due_collections(today)
        notified = notify_due_collections(today)
        self.stdout.write(
            f"Created {len(created)} collection(s), notified {len(notified)}."
        )
