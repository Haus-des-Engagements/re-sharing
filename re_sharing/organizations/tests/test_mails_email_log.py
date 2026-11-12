"""The emails of the platform end up in the email log with type and links."""

from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from psycopg.types.range import Range

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.emails.models import EmailLog
from re_sharing.emails.tests.helpers import with_email_log
from re_sharing.emails.tests.helpers import with_failing_email_log
from re_sharing.organizations.mails import _log_links
from re_sharing.organizations.mails import send_booking_confirmation_email
from re_sharing.organizations.mails import send_custom_organization_email
from re_sharing.organizations.mails import send_email_with_template
from re_sharing.organizations.mails import send_permanent_code_created_email
from re_sharing.organizations.mails import send_permanent_code_invalidated_email
from re_sharing.organizations.mails import send_permanent_code_renewed_email
from re_sharing.organizations.models import EmailTemplate
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import EmailTemplateFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.tests.factories import PermanentCodeFactory

EmailType = EmailTemplate.EmailTypeChoices


class LogLinksTest(TestCase):
    def test_booking_and_its_organization(self):
        booking = BookingFactory()

        assert _log_links({"booking": booking}) == {
            "booking": booking,
            "organization": booking.organization,
        }

    def test_organization_of_a_booking_series(self):
        series = BookingSeriesFactory()

        assert _log_links({"booking_series": series}) == {
            "booking": None,
            "organization": series.organization,
        }

    def test_explicit_organization_wins(self):
        booking = BookingFactory()
        organization = OrganizationFactory()

        links = _log_links({"booking": booking, "organization": organization})

        assert links == {"booking": booking, "organization": organization}

    def test_context_without_either(self):
        assert _log_links({"domain": "example.org"}) == {
            "booking": None,
            "organization": None,
        }


@with_email_log
class TemplateEmailLogTest(TestCase):
    def test_booking_email_is_logged_with_type_booking_and_organization(self):
        EmailTemplateFactory(
            email_type=EmailType.BOOKING_CONFIRMATION,
            subject="Confirmed: {{ booking.title }}",
            body="Your booking {{ booking.title }} is confirmed",
            active=True,
        )
        start = timezone.now() + timedelta(days=10)
        booking = BookingFactory(
            title="Team day", timespan=Range(start, start + timedelta(hours=2))
        )

        send_booking_confirmation_email.call(booking.id)

        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.SENT
        assert entry.email_type == EmailType.BOOKING_CONFIRMATION
        assert entry.booking == booking
        assert entry.organization == booking.organization
        assert entry.subject == "Confirmed: Team day"
        assert entry.body_text == "Your booking Team day is confirmed"
        assert entry.to == mail.outbox[0].to

    def test_attachment_is_recorded_by_name(self):
        EmailTemplateFactory(
            email_type=EmailType.BOOKING_CONFIRMATION, subject="S", body="B"
        )
        booking = BookingFactory()

        send_email_with_template(
            EmailType.BOOKING_CONFIRMATION,
            {"booking": booking},
            ["a@example.org"],
            ical_content=b"BEGIN:VCALENDAR",
        )

        entry = EmailLog.objects.get()
        assert entry.attachment_names == [f"booking_{booking.slug}.ics"]

    @override_settings(DEFAULT_BCC_EMAIL=None)
    def test_no_blind_copy_without_a_configured_address(self):
        EmailTemplateFactory(
            email_type=EmailType.BOOKING_CONFIRMATION, subject="S", body="B"
        )

        send_email_with_template(
            EmailType.BOOKING_CONFIRMATION,
            {"booking": BookingFactory()},
            ["a@example.org"],
        )

        assert mail.outbox[0].bcc == []
        assert EmailLog.objects.get().bcc == []

    @override_settings(DEFAULT_BCC_EMAIL="copy@example.org")
    def test_blind_copy_with_a_configured_address(self):
        EmailTemplateFactory(
            email_type=EmailType.BOOKING_CONFIRMATION, subject="S", body="B"
        )

        send_email_with_template(
            EmailType.BOOKING_CONFIRMATION,
            {"booking": BookingFactory()},
            ["a@example.org"],
        )

        assert mail.outbox[0].bcc == ["copy@example.org"]
        assert EmailLog.objects.get().bcc == ["copy@example.org"]


@with_email_log
class OwnMessageEmailLogTest(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory(
            email="org@example.org", status=Organization.Status.CONFIRMED
        )

    def test_custom_email(self):
        send_custom_organization_email.call(
            self.organization.id,
            subject_template="Hello {{ organization.name }}",
            body_template="<p>Dear <strong>all</strong></p>",
        )

        entry = EmailLog.objects.get()
        assert entry.email_type == "custom"
        assert entry.organization == self.organization
        assert entry.subject == f"Hello {self.organization.name}"
        assert entry.body_text == "Dear all"
        assert "<p>Dear <strong>all</strong></p>" in entry.body_html
        assert entry.to == ["org@example.org"]

    def test_test_email_is_logged_with_the_test_recipient(self):
        send_custom_organization_email.call(
            self.organization.id,
            subject_template="Hello",
            body_template="<p>Body</p>",
            recipient_override="me@example.org",
        )

        entry = EmailLog.objects.get()
        assert entry.to == ["me@example.org"]
        assert entry.subject == "[Test] Hello"
        assert entry.organization == self.organization

    def test_permanent_code_emails(self):
        for email_type in (
            EmailType.PERMANENT_CODE_CREATED,
            EmailType.PERMANENT_CODE_RENEWED,
            EmailType.PERMANENT_CODE_INVALIDATED,
        ):
            EmailTemplateFactory(
                email_type=email_type, subject="Code", body="{{ code }}", active=True
            )
        code = PermanentCodeFactory(organization=self.organization)
        new_code = PermanentCodeFactory(organization=self.organization)

        send_permanent_code_created_email.call(code.id)
        send_permanent_code_renewed_email.call(new_code.id, code.id)
        send_permanent_code_invalidated_email.call(code.id)

        entries = EmailLog.objects.order_by("id")
        assert [entry.email_type for entry in entries] == [
            EmailType.PERMANENT_CODE_CREATED,
            EmailType.PERMANENT_CODE_RENEWED,
            EmailType.PERMANENT_CODE_INVALIDATED,
        ]
        assert all(entry.organization == self.organization for entry in entries)


@with_failing_email_log
class FailedCustomEmailLogTest(TestCase):
    def test_rejected_custom_email_is_logged_as_failed(self):
        organization = OrganizationFactory(
            email="org@example.org", status=Organization.Status.CONFIRMED
        )

        result = send_custom_organization_email.call(
            organization.id, subject_template="Hello", body_template="<p>Body</p>"
        )

        assert result == {"sent": False, "reason": "smtp_error"}
        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.FAILED
        assert "550 Mailbox unavailable" in entry.error
        assert entry.organization == organization
        assert entry.subject == "Hello"
