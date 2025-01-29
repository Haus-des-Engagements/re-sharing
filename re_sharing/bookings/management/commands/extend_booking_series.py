from django.core.management.base import BaseCommand

from re_sharing.bookings.services_booking_series import extend_booking_series


class Command(BaseCommand):
    help = "Extend booking series"

    def handle(self, *args, **kwargs):
        # Call your function here
        new_bookings = extend_booking_series()
        # Optionally, log the result
        self.stdout.write(self.style.SUCCESS(f"Created bookings: {new_bookings}"))
