from unittest.mock import patch

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.test import TestCase

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.emails.models import EmailLog
from re_sharing.emails.services import set_email_log_context
from re_sharing.emails.tests.factories import EmailLogFactory
from re_sharing.emails.tests.helpers import with_email_log
from re_sharing.emails.tests.helpers import with_failing_email_log
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.users.tests.factories import UserFactory


def _message(**kwargs):
    defaults = {
        "subject": "Hello",
        "body": "Plain text",
        "from_email": "sender@example.org",
        "to": ["a@example.org"],
    }
    defaults.update(kwargs)
    return EmailMessage(**defaults)


@with_email_log
class LoggingEmailBackendTest(TestCase):
    def test_sent_email_is_recorded(self):
        message = _message(
            to=["a@example.org", "b@example.org", "c@example.org"],
            cc=["cc@example.org"],
            bcc=["bcc@example.org"],
        )
        message.attach("booking.ics", b"BEGIN:VCALENDAR", "text/calendar")

        assert message.send() == 1

        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.SENT
        assert entry.sent_at is not None
        assert entry.error == ""
        assert entry.attempts == 1
        assert entry.from_email == "sender@example.org"
        assert entry.to == ["a@example.org", "b@example.org", "c@example.org"]
        assert entry.cc == ["cc@example.org"]
        assert entry.bcc == ["bcc@example.org"]
        assert entry.subject == "Hello"
        assert entry.body_text == "Plain text"
        assert entry.body_html == ""
        assert entry.attachment_names == ["booking.ics"]
        assert len(mail.outbox) == 1

    def test_html_alternative_is_recorded(self):
        message = EmailMultiAlternatives(
            subject="Hello", body="Plain text", to=["a@example.org"]
        )
        message.attach_alternative("<p>Formatted</p>", "text/html")

        message.send()

        entry = EmailLog.objects.get()
        assert entry.body_text == "Plain text"
        assert entry.body_html == "<p>Formatted</p>"

    def test_html_only_email_is_recorded_as_html(self):
        message = _message(body="<p>Formatted</p>")
        message.content_subtype = "html"

        message.send()

        entry = EmailLog.objects.get()
        assert entry.body_text == ""
        assert entry.body_html == "<p>Formatted</p>"

    def test_email_without_context_has_no_type_or_links(self):
        send_mail("Reset your password", "Link", None, ["a@example.org"])

        entry = EmailLog.objects.get()
        assert entry.subject == "Reset your password"
        assert entry.body_text == "Link"
        assert entry.email_type == ""
        assert entry.organization is None
        assert entry.booking is None
        assert entry.user is None

    def test_context_sets_type_and_links(self):
        booking = BookingFactory()
        user = UserFactory()
        message = set_email_log_context(
            _message(),
            email_type="booking_confirmation",
            organization=booking.organization,
            booking=booking,
            user=user,
        )

        message.send()

        entry = EmailLog.objects.get()
        assert entry.email_type == "booking_confirmation"
        assert entry.organization == booking.organization
        assert entry.booking == booking
        assert entry.user == user

    def test_existing_entry_is_updated_instead_of_a_new_one_created(self):
        organization = OrganizationFactory()
        entry = EmailLogFactory(
            status=EmailLog.Status.FAILED,
            error="550 Mailbox unavailable",
            attempts=1,
            organization=organization,
            email_type="custom",
        )
        message = set_email_log_context(_message(), log_entry=entry)

        message.send()

        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.SENT
        assert entry.error == ""
        assert entry.attempts == 2  # noqa: PLR2004
        assert entry.sent_at is not None
        assert entry.organization == organization
        assert entry.email_type == "custom"

    def test_several_messages_in_one_call(self):
        connection = mail.get_connection()

        sent = connection.send_messages(
            [_message(subject="One"), _message(subject="Two")]
        )

        assert sent == 2  # noqa: PLR2004
        assert set(EmailLog.objects.values_list("subject", flat=True)) == {
            "One",
            "Two",
        }

    def test_message_without_recipients_is_recorded_as_failed(self):
        with patch(
            "django.core.mail.backends.locmem.EmailBackend.send_messages",
            return_value=0,
        ):
            sent = mail.get_connection().send_messages([_message()])

        assert sent == 0
        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.FAILED
        assert entry.error

    def test_failing_log_write_does_not_stop_the_email(self):
        with patch(
            "re_sharing.emails.services._write_entry", side_effect=RuntimeError("boom")
        ):
            assert _message().send() == 1

        assert len(mail.outbox) == 1
        assert not EmailLog.objects.exists()

    def test_open_and_close_are_passed_on(self):
        connection = mail.get_connection()

        connection.open()
        connection.close()


@with_failing_email_log
class LoggingEmailBackendFailureTest(TestCase):
    def test_rejected_email_is_recorded_and_the_error_raised(self):
        with pytest.raises(ConnectionError):
            _message().send()

        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.FAILED
        assert "550 Mailbox unavailable" in entry.error
        assert entry.sent_at is None
        assert entry.attempts == 1
        assert entry.subject == "Hello"

    def test_fail_silently_swallows_the_error_but_records_it(self):
        assert _message().send(fail_silently=True) == 0

        assert EmailLog.objects.get().status == EmailLog.Status.FAILED

    def test_failed_retry_keeps_the_entry_failed_with_the_new_error(self):
        entry = EmailLogFactory(
            status=EmailLog.Status.FAILED, error="old error", attempts=1
        )
        message = set_email_log_context(_message(), log_entry=entry)

        message.send(fail_silently=True)

        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.FAILED
        assert "550" in entry.error
        assert entry.attempts == 2  # noqa: PLR2004
