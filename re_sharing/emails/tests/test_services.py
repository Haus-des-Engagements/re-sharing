from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock

from django.core import mail
from django.test import TestCase
from django.test import override_settings
from freezegun import freeze_time

from re_sharing.emails.models import EmailLog
from re_sharing.emails.services import enqueue_spaced
from re_sharing.emails.services import resend_emails
from re_sharing.emails.tasks import resend_email
from re_sharing.emails.tests.factories import EmailLogFactory
from re_sharing.emails.tests.helpers import with_email_log
from re_sharing.emails.tests.helpers import with_failing_email_log
from re_sharing.organizations.tests.factories import OrganizationFactory


def _delaying_task():
    """A task whose backend can delay; records how each run was scheduled."""
    task = MagicMock()
    task.get_backend.return_value.supports_defer = True
    return task


@freeze_time("2026-11-12 10:00:00")
class EnqueueSpacedTest(TestCase):
    @override_settings(BULK_EMAIL_SEND_INTERVAL=5)
    def test_each_task_starts_one_interval_after_the_previous(self):
        task = _delaying_task()

        count = enqueue_spaced(task, [(1,), (2,), (3,)])

        assert count == 3  # noqa: PLR2004
        # the first starts at once, the others are delayed
        task.enqueue.assert_called_once_with(1)
        start = datetime(2026, 11, 12, 10, 0, 0, tzinfo=UTC)
        assert [call.kwargs for call in task.using.call_args_list] == [
            {"run_after": start + timedelta(seconds=5)},
            {"run_after": start + timedelta(seconds=10)},
        ]
        assert [
            call.args for call in task.using.return_value.enqueue.call_args_list
        ] == [(2,), (3,)]

    @override_settings(BULK_EMAIL_SEND_INTERVAL=0)
    def test_interval_zero_starts_all_at_once(self):
        task = _delaying_task()

        enqueue_spaced(task, [(1,), (2,)])

        task.using.assert_not_called()
        assert [call.args for call in task.enqueue.call_args_list] == [(1,), (2,)]

    @override_settings(BULK_EMAIL_SEND_INTERVAL=5)
    def test_backend_that_cannot_delay_starts_all_at_once(self):
        task = MagicMock()
        task.get_backend.return_value.supports_defer = False

        enqueue_spaced(task, [(1,), (2,)])

        task.using.assert_not_called()
        assert task.enqueue.call_count == 2  # noqa: PLR2004


class ResendEmailTest(TestCase):
    def _failed_entry(self, **kwargs):
        defaults = {
            "status": EmailLog.Status.FAILED,
            "error": "550 Mailbox unavailable",
            "to": ["org@example.org"],
            "cc": ["cc@example.org"],
            "bcc": ["bcc@example.org"],
            "subject": "Stored subject",
            "body_text": "Stored text",
            "body_html": "<p>Stored text</p>",
            "email_type": "custom",
            "organization": OrganizationFactory(),
        }
        defaults.update(kwargs)
        return EmailLogFactory(**defaults)

    @with_email_log
    def test_failed_entry_becomes_sent_with_the_stored_content(self):
        entry = self._failed_entry()

        result = resend_email.call(entry.pk, True)  # noqa: FBT003

        assert result == {"sent": True, "email_log_id": entry.pk}
        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.SENT
        assert entry.error == ""
        assert entry.attempts == 2  # noqa: PLR2004
        message = mail.outbox[0]
        assert message.to == ["org@example.org"]
        assert message.cc == ["cc@example.org"]
        assert message.bcc == ["bcc@example.org"]
        assert message.subject == "Stored subject"
        assert message.body == "Stored text"
        assert message.alternatives[0][0] == "<p>Stored text</p>"

    @with_failing_email_log
    def test_failed_entry_stays_failed_with_the_new_error(self):
        entry = self._failed_entry(error="old error")

        result = resend_email.call(entry.pk, True)  # noqa: FBT003

        assert result == {"sent": False, "reason": "smtp_error"}
        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.FAILED
        assert "550" in entry.error
        assert entry.attempts == 2  # noqa: PLR2004

    @with_email_log
    def test_retry_is_not_delivered_twice(self):
        entry = self._failed_entry()
        resend_email.call(entry.pk, True)  # noqa: FBT003

        result = resend_email.call(entry.pk, True)  # noqa: FBT003

        assert result == {"sent": False, "reason": "already_sent"}
        assert len(mail.outbox) == 1
        assert EmailLog.objects.get().attempts == 2  # noqa: PLR2004

    @with_email_log
    def test_sent_entry_is_sent_as_a_new_entry(self):
        original = self._failed_entry(
            status=EmailLog.Status.SENT, error="", attachment_names=["booking.ics"]
        )

        resend_email.call(original.pk, False)  # noqa: FBT003

        assert len(mail.outbox) == 1
        assert mail.outbox[0].attachments == []
        copy = EmailLog.objects.exclude(pk=original.pk).get()
        assert copy.status == EmailLog.Status.SENT
        assert copy.email_type == "custom"
        assert copy.organization == original.organization
        assert copy.subject == "Stored subject"
        assert copy.attempts == 1
        original.refresh_from_db()
        assert original.attempts == 1
        assert original.attachment_names == ["booking.ics"]

    @with_email_log
    def test_html_only_entry_is_sent_as_html(self):
        entry = self._failed_entry(body_text="", body_html="<p>Only HTML</p>")

        resend_email.call(entry.pk, True)  # noqa: FBT003

        message = mail.outbox[0]
        assert message.content_subtype == "html"
        assert message.body == "<p>Only HTML</p>"
        entry.refresh_from_db()
        assert entry.body_text == ""
        assert entry.body_html == "<p>Only HTML</p>"

    @with_email_log
    def test_resend_emails_retries_failed_and_copies_sent_entries(self):
        failed = self._failed_entry()
        sent = self._failed_entry(status=EmailLog.Status.SENT, error="")

        count = resend_emails([failed, sent])

        assert count == 2  # noqa: PLR2004
        assert len(mail.outbox) == 2  # noqa: PLR2004
        failed.refresh_from_db()
        assert failed.status == EmailLog.Status.SENT
        assert EmailLog.objects.count() == 3  # noqa: PLR2004
