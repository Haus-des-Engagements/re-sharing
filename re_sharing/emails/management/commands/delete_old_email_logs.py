from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from re_sharing.emails.models import EmailLog


class Command(BaseCommand):
    help = (
        "Delete the entries of the email log that are older than "
        "EMAIL_LOG_RETENTION_MONTHS months. Meant to run once a day."
    )

    def handle(self, *args, **options):
        months = settings.EMAIL_LOG_RETENTION_MONTHS
        limit = timezone.now() - relativedelta(months=months)
        deleted, _details = EmailLog.objects.filter(created__lt=limit).delete()
        self.stdout.write(
            f"Deleted {deleted} email log entries older than {months} months."
        )
