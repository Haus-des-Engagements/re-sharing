from datetime import UTC
from datetime import datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from freezegun import freeze_time

from re_sharing.emails.models import EmailLog
from re_sharing.emails.tests.factories import EmailLogFactory


class DeleteOldEmailLogsTest(TestCase):
    def _entry(self, created, subject):
        with freeze_time(created):
            return EmailLogFactory(subject=subject)

    @override_settings(EMAIL_LOG_RETENTION_MONTHS=12)
    def test_deletes_entries_older_than_the_retention(self):
        self._entry(datetime(2025, 10, 12, tzinfo=UTC), "13 months old")
        self._entry(datetime(2025, 12, 12, tzinfo=UTC), "11 months old")
        self._entry(datetime(2026, 11, 11, tzinfo=UTC), "yesterday")
        output = StringIO()

        with freeze_time(datetime(2026, 11, 12, tzinfo=UTC)):
            call_command("delete_old_email_logs", stdout=output)

        assert set(EmailLog.objects.values_list("subject", flat=True)) == {
            "11 months old",
            "yesterday",
        }
        assert "Deleted 1 email log entries older than 12 months." in output.getvalue()

    @override_settings(EMAIL_LOG_RETENTION_MONTHS=1)
    def test_retention_is_configurable(self):
        self._entry(datetime(2026, 9, 1, tzinfo=UTC), "old")
        self._entry(datetime(2026, 11, 1, tzinfo=UTC), "recent")

        with freeze_time(datetime(2026, 11, 12, tzinfo=UTC)):
            call_command("delete_old_email_logs", stdout=StringIO())

        assert list(EmailLog.objects.values_list("subject", flat=True)) == ["recent"]
