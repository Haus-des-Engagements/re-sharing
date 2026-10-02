from collections import Counter

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from re_sharing.bookings.services_quota_transition import apply_free_bookings_quota
from re_sharing.organizations.selectors import get_limited_organizations


class Command(BaseCommand):
    help = (
        "Bring bookings created before the free bookings quota under the quota "
        "for every organization with a limited allowance."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute and print the report, change nothing.",
        )
        parser.add_argument(
            "--organizations",
            nargs="*",
            metavar="SLUG",
            help="Only process these organizations (slugs).",
        )

    def handle(self, *args, **options):
        organizations = get_limited_organizations()
        slugs = options["organizations"]
        if slugs:
            organizations = organizations.filter(slug__in=slugs)
            missing = set(slugs) - set(organizations.values_list("slug", flat=True))
            if missing:
                msg = (
                    f"Unknown or unlimited organizations: {', '.join(sorted(missing))}"
                )
                raise CommandError(msg)

        dry_run = options["dry_run"]
        verbosity = options["verbosity"]
        prefix = "DRY RUN: " if dry_run else ""
        totals = Counter()
        failed = []
        for organization in organizations:
            try:
                report = apply_free_bookings_quota(organization, dry_run=dry_run)
            except Exception as error:  # noqa: BLE001
                failed.append(organization)
                self.stderr.write(f"{prefix}{organization.name}: failed ({error})")
                continue
            self._write_report(report, prefix, verbosity)
            totals["kept_free"] += len(report.kept_free)
            totals["charged"] += len(report.charged)
            totals["deleted"] += len(report.deleted)
            totals["cancelled"] += len(report.cancelled)
            totals["series"] += len(report.updated_series)

        self.stdout.write(
            f"{prefix}Total: {totals['kept_free']} kept free, "
            f"{totals['charged']} charged, {totals['deleted']} deleted, "
            f"{totals['cancelled']} cancelled, {totals['series']} series updated"
        )
        if failed:
            msg = f"{len(failed)} organization(s) failed"
            raise CommandError(msg)

    def _write_report(self, report, prefix, verbosity):
        name = report.organization.name
        if report.nothing_to_do:
            self.stdout.write(f"{prefix}{name}: nothing to do")
            return
        self.stdout.write(
            f"{prefix}{name}: {len(report.kept_free)} kept free, "
            f"{len(report.charged)} charged ({report.charged_total:.2f} €), "
            f"{len(report.deleted)} deleted, {len(report.cancelled)} cancelled, "
            f"{len(report.updated_series)} series updated"
        )
        for year, numbers in sorted(report.allowance_by_year.items()):
            self.stdout.write(
                f"  {year}: allowance {numbers['allowance']}, "
                f"remaining before run {numbers['remaining']}"
            )
        if verbosity < 2:  # noqa: PLR2004
            return
        for booking in report.kept_free:
            self.stdout.write(f"  {booking.start_date} {booking.resource}: free")
        for booking in report.charged:
            self.stdout.write(
                f"  {booking.start_date} {booking.resource}: charged "
                f"{booking.total_amount:.2f} € ({booking.compensation.name})"
            )
        for removed in report.deleted:
            self.stdout.write(f"  {removed.start_date} {removed.resource}: deleted")
        for booking in report.cancelled:
            self.stdout.write(f"  {booking.start_date} {booking.resource}: cancelled")
        for series in report.updated_series:
            fallback = series.fallback_compensation
            self.stdout.write(
                f"  series '{series.title}': fallback "
                f"{fallback.name if fallback else 'none'}"
            )
