from django.core.management.base import BaseCommand
from django.utils import timezone

from re_sharing.agreements.services_collections import detect_returns
from re_sharing.agreements.services_collections import mark_collected
from re_sharing.agreements.services_collections import sync_invoice_payments


class Command(BaseCommand):
    help = (
        "Mark debits collected after the return window, detect returns in the "
        "bank transactions and sync paid return invoices."
    )

    def handle(self, *args, **options):
        collected = mark_collected(timezone.localdate())
        returns = detect_returns()
        invoices = sync_invoice_payments()
        self.stdout.write(
            f"Collected {collected}, returns {returns}, invoices {invoices}."
        )
