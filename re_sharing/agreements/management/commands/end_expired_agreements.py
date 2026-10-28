from django.core.management.base import BaseCommand
from django.utils import timezone

from re_sharing.agreements.services import end_expired_agreements


class Command(BaseCommand):
    help = "End active agreements whose end date has passed."

    def handle(self, *args, **options):
        ended = end_expired_agreements(timezone.localdate())
        self.stdout.write(f"Ended {len(ended)} agreement(s).")
