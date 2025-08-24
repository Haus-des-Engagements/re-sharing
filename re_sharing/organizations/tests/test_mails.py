from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from psycopg.types.range import Range

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.organizations.mails import booking_ics
from re_sharing.organizations.mails import get_recipient_booking
from re_sharing.organizations.mails import get_recipient_booking_series
from re_sharing.organizations.mails import organization_cancellation_email
from re_sharing.organizations.mails import organization_confirmation_email
from re_sharing.organizations.mails import send_booking_cancellation_email
from re_sharing.organizations.mails import send_booking_confirmation_email
from re_sharing.organizations.mails import send_booking_reminder_emails
from re_sharing.organizations.mails import send_booking_series_cancellation_email
from re_sharing.organizations.mails import send_booking_series_confirmation_email
from re_sharing.organizations.mails import send_email_with_template
from re_sharing.organizations.mails import send_manager_new_booking_email
from re_sharing.organizations.mails import send_manager_new_booking_series_email
from re_sharing.organizations.mails import send_monthly_bookings_overview
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import EmailTemplate
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import EmailTemplateFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


class GetRecipientBookingTest(TestCase):
    def test_recipient_is_user_email_when_org_setting_false(self):
        user = UserFactory(email="user@example.com")
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=False
        )
        booking = BookingFactory(user=user, organization=organization)
        BookingPermissionFactory(user=user, organization=organization)

        result = get_recipient_booking(booking)

        assert result == ["user@example.com"]

    def test_recipient_is_organization_email_when_org_setting_true(self):
        user = UserFactory(email="user@example.com")
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=True
        )
        booking = BookingFactory(user=user, organization=organization)

        result = get_recipient_booking(booking)

        assert result == ["org@example.com"]


class GetRecipientBookingSeriesTest(TestCase):
    def test_recipient_is_user_email_when_org_setting_false(self):
        user = UserFactory(email="user@example.com")
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=False
        )
        booking_series = BookingSeriesFactory(user=user, organization=organization)

        result = get_recipient_booking_series(booking_series)

        assert result == ["user@example.com"]

    def test_recipient_is_organization_email_when_org_setting_true(self):
        user = UserFactory(email="user@example.com")
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=True
        )
        booking_series = BookingSeriesFactory(user=user, organization=organization)

        result = get_recipient_booking_series(booking_series)

        assert result == ["org@example.com"]


class BookingIcsTest(TestCase):
    def test_booking_ics_generates_calendar_content(self):
        resource = ResourceFactory(name="Test Resource")
        start = timezone.now()
        end = timezone.now() + timedelta(hours=2)
        booking = BookingFactory(
            title="Test Booking", resource=resource, timespan=Range(start, end)
        )

        result = booking_ics(booking)

        # Test that it returns calendar data
        assert b"BEGIN:VCALENDAR" in result
        assert b"BEGIN:VEVENT" in result
        assert b"Test Booking" in result
        assert b"Test Resource" in result

    def test_booking_ics_includes_location_when_available(self):
        resource = ResourceFactory(name="Test Resource")
        resource.location.address = "123 Test Street"
        resource.location.save()
        booking = BookingFactory(resource=resource)

        result = booking_ics(booking)

        assert b"123 Test Street" in result


class SendEmailWithTemplateTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_email_when_template_exists_and_active(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
            subject="Test Subject: {{ booking.title }}",
            body="Test Body for {{ booking.title }}",
            active=True,
        )
        booking = BookingFactory(title="My Booking")
        context = {"booking": booking, "domain": "example.com"}

        send_email_with_template(
            EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
            context,
            ["test@example.com"],
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Test Subject: My Booking"
        assert "Test Body for My Booking" in mail.outbox[0].body
        assert mail.outbox[0].to == ["test@example.com"]

    def test_does_not_send_email_when_template_inactive(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION, active=False
        )
        booking = BookingFactory()
        context = {"booking": booking}

        send_email_with_template(
            EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
            context,
            ["test@example.com"],
        )

        assert len(mail.outbox) == 0

    def test_does_not_send_email_when_template_does_not_exist(self):
        booking = BookingFactory()
        context = {"booking": booking}

        send_email_with_template("nonexistent_type", context, ["test@example.com"])

        assert len(mail.outbox) == 0

    def test_attaches_ical_when_provided(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION, active=True
        )
        start = timezone.now()
        end = timezone.now() + timedelta(hours=2)
        booking = BookingFactory(slug="test-booking", timespan=Range(start, end))
        context = {"booking": booking}
        ical_content = "BEGIN:VCALENDAR\nEND:VCALENDAR"

        send_email_with_template(
            EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
            context,
            ["test@example.com"],
            ical_content=ical_content,
        )

        assert len(mail.outbox) == 1
        assert len(mail.outbox[0].attachments) == 1
        assert mail.outbox[0].attachments[0][0].startswith("booking_")
        assert mail.outbox[0].attachments[0][0].endswith(".ics")


class SendBookingConfirmationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_confirmation_email(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_CONFIRMATION,
            subject="Booking confirmed: {{ booking.title }}",
            body="Your booking {{ booking.title }} is confirmed",
            active=True,
        )
        start = timezone.now() + timedelta(days=10)
        end = timezone.now() + timedelta(days=10, hours=2)
        booking = BookingFactory(title="Test Booking", timespan=Range(start, end))

        send_booking_confirmation_email(booking)

        assert len(mail.outbox) == 1
        assert "Booking confirmed: Test Booking" in mail.outbox[0].subject
        assert "Your booking Test Booking is confirmed" in mail.outbox[0].body
        # The booking confirmation doesn't attach ICS by default


class SendBookingCancellationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_cancellation_email(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_CANCELLATION,
            subject="Booking cancelled: {{ booking.title }}",
            body="Your booking {{ booking.title }} has been cancelled",
            active=True,
        )
        booking = BookingFactory(title="Test Booking")

        send_booking_cancellation_email(booking)

        assert len(mail.outbox) == 1
        assert "Booking cancelled: Test Booking" in mail.outbox[0].subject
        assert "Your booking Test Booking has been cancelled" in mail.outbox[0].body


class SendBookingReminderEmailsTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_REMINDER,
            subject="Booking reminder: {{ booking.title }}",
            body="Reminder for {{ booking.title }}",
            active=True,
        )

    def test_sends_reminder_for_booking_in_5_days(self):
        future_time = timezone.now() + timedelta(days=5)
        future_time = future_time.replace(hour=10, minute=0, second=0, microsecond=0)
        booking = BookingFactory(
            title="Future Booking",
            status=BookingStatus.CONFIRMED,
            timespan=Range(future_time, future_time + timedelta(hours=2)),
        )

        slugs, date = send_booking_reminder_emails(days=5)

        assert len(mail.outbox) == 1
        assert booking.slug in slugs
        assert "Booking reminder: Future Booking" in mail.outbox[0].subject

    def test_does_not_send_reminder_for_booking_too_far_future(self):
        future_time = timezone.now() + timedelta(days=10)
        BookingFactory(
            status=BookingStatus.CONFIRMED,
            timespan=Range(future_time, future_time + timedelta(hours=2)),
        )

        slugs, date = send_booking_reminder_emails(days=5)

        assert len(mail.outbox) == 0
        assert len(slugs) == 0

    def test_does_not_send_reminder_for_unconfirmed_booking(self):
        future_time = timezone.now() + timedelta(days=5)
        future_time = future_time.replace(hour=10, minute=0, second=0, microsecond=0)
        BookingFactory(
            status=BookingStatus.PENDING,
            timespan=Range(future_time, future_time + timedelta(hours=2)),
        )

        slugs, date = send_booking_reminder_emails(days=5)

        assert len(mail.outbox) == 0
        assert len(slugs) == 0


class SendManagerNewBookingEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    @patch(
        "re_sharing.organizations.mails.settings.DEFAULT_MANAGER_EMAIL",
        "manager@example.com",
    )
    def test_sends_manager_notification(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.MANAGER_NEW_BOOKING,
            subject="New booking: {{ booking.title }}",
            body="New booking created: {{ booking.title }}",
            active=True,
        )
        booking = BookingFactory(title="Test Booking")

        send_manager_new_booking_email(booking)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["manager@example.com"]
        assert "New booking: Test Booking" in mail.outbox[0].subject


class SendBookingSeriesConfirmationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_series_confirmation_email(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_SERIES_CONFIRMATION,
            subject="Series confirmed",
            body="Your booking series is confirmed",
            active=True,
        )
        booking_series = BookingSeriesFactory()

        send_booking_series_confirmation_email(booking_series)

        assert len(mail.outbox) == 1
        assert "Series confirmed" in mail.outbox[0].subject


class SendBookingSeriesCancellationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_series_cancellation_email(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_SERIES_CANCELLATION,
            subject="Series cancelled",
            body="Your booking series has been cancelled",
            active=True,
        )
        booking_series = BookingSeriesFactory()

        send_booking_series_cancellation_email(booking_series)

        assert len(mail.outbox) == 1
        assert "Series cancelled" in mail.outbox[0].subject


class SendManagerNewBookingSeriesEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    @patch(
        "re_sharing.organizations.mails.settings.DEFAULT_MANAGER_EMAIL",
        "manager@example.com",
    )
    def test_sends_manager_series_notification(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.MANAGER_NEW_BOOKING_SERIES,
            subject="New booking series",
            body="New booking series created",
            active=True,
        )
        booking_series = BookingSeriesFactory()

        send_manager_new_booking_series_email(booking_series)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["manager@example.com"]


class OrganizationConfirmationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_to_organization_email_when_setting_enabled(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.ORGANIZATION_CONFIRMATION,
            subject="Organization confirmed",
            body="Your organization is confirmed",
            active=True,
        )
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=True
        )

        organization_confirmation_email(organization)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["org@example.com"]

    def test_sends_to_admin_emails_when_setting_disabled(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.ORGANIZATION_CONFIRMATION,
            subject="Organization confirmed",
            body="Your organization is confirmed",
            active=True,
        )
        admin_user = UserFactory(email="admin@example.com")
        organization = OrganizationFactory(
            send_booking_emails_only_to_organization=False
        )
        BookingPermissionFactory(
            user=admin_user,
            organization=organization,
            role=BookingPermission.Role.ADMIN,
            status=BookingPermission.Status.CONFIRMED,
        )

        organization_confirmation_email(organization)

        assert len(mail.outbox) == 1
        assert "admin@example.com" in mail.outbox[0].to


class OrganizationCancellationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_cancellation_email(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.ORGANIZATION_CANCELLATION,
            subject="Organization cancelled",
            body="Your organization has been cancelled",
            active=True,
        )
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=True
        )

        organization_cancellation_email(organization)

        assert len(mail.outbox) == 1
        assert "Organization cancelled" in mail.outbox[0].subject


class SendMonthlyBookingsOverviewTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.MONTHLY_BOOKINGS,
            subject="Monthly bookings overview",
            body="Your monthly bookings: {% for booking in bookings %}"
            "{{ booking.title }}{% endfor %}",
            active=True,
        )

    def test_sends_monthly_overview_for_organizations_with_bulk_access_codes(self):
        organization = OrganizationFactory(
            email="org@example.com", monthly_bulk_access_codes=True
        )
        next_month = timezone.now() + timedelta(days=32)
        BookingFactory(
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(next_month, next_month + timedelta(hours=2)),
            title="Next Month Booking",
        )

        result = send_monthly_bookings_overview()

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["org@example.com"]
        assert result["organizations_processed"] == 1
        assert organization.name in result["organizations_list"]

    def test_does_not_send_for_organizations_without_bulk_access_codes(self):
        organization = OrganizationFactory(monthly_bulk_access_codes=False)
        next_month = timezone.now() + timedelta(days=32)
        BookingFactory(
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(next_month, next_month + timedelta(hours=2)),
        )

        result = send_monthly_bookings_overview()

        assert len(mail.outbox) == 0
        assert result["organizations_processed"] == 0
