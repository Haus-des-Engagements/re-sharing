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
from re_sharing.organizations.mails import send_booking_not_available_email
from re_sharing.organizations.mails import send_booking_reminder_email
from re_sharing.organizations.mails import send_booking_series_cancellation_email
from re_sharing.organizations.mails import send_booking_series_confirmation_email
from re_sharing.organizations.mails import send_custom_organization_email
from re_sharing.organizations.mails import send_email_with_template
from re_sharing.organizations.mails import send_manager_new_booking_email
from re_sharing.organizations.mails import send_manager_new_booking_series_email
from re_sharing.organizations.mails import send_monthly_overview_email
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.models import EmailTemplate
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import EmailTemplateFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.tests.factories import AccessFactory
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

        send_booking_confirmation_email.call(booking.id)

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

        send_booking_cancellation_email.call(booking.id)

        assert len(mail.outbox) == 1
        assert "Booking cancelled: Test Booking" in mail.outbox[0].subject
        assert "Your booking Test Booking has been cancelled" in mail.outbox[0].body


class SendBookingNotAvailableEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_sends_not_available_email(self):
        """
        Test that booking not available email is sent when template is active
        """
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_NOT_AVAILABLE,
            subject="Booking not available: {{ booking.title }}",
            body=(
                "Unfortunately, the resource for {{ booking.title }} "
                "is no longer available at the requested time."
            ),
            active=True,
        )
        booking = BookingFactory(title="Test Booking", status=BookingStatus.UNAVAILABLE)

        send_booking_not_available_email.call(booking.id)

        assert len(mail.outbox) == 1
        assert "Booking not available: Test Booking" in mail.outbox[0].subject
        assert (
            "Unfortunately, the resource for Test Booking is no longer available"
            in mail.outbox[0].body
        )

    def test_does_not_send_email_when_template_inactive(self):
        """Test that no email is sent when template is inactive"""
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_NOT_AVAILABLE,
            active=False,
        )
        booking = BookingFactory(status=BookingStatus.UNAVAILABLE)

        send_booking_not_available_email.call(booking.id)

        assert len(mail.outbox) == 0

    def test_does_not_send_email_when_template_does_not_exist(self):
        """Test that no email is sent when template does not exist"""
        booking = BookingFactory(status=BookingStatus.UNAVAILABLE)

        send_booking_not_available_email.call(booking.id)

        assert len(mail.outbox) == 0

    def test_sends_to_correct_recipient_user(self):
        """Test that email is sent to the correct recipient (user)"""
        user = UserFactory(email="user@example.com")
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=False
        )
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_NOT_AVAILABLE,
            subject="Not available",
            body="Not available",
            active=True,
        )
        booking = BookingFactory(
            user=user, organization=organization, status=BookingStatus.UNAVAILABLE
        )
        BookingPermissionFactory(user=user, organization=organization)

        send_booking_not_available_email.call(booking.id)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["user@example.com"]

    def test_sends_to_correct_recipient_organization(self):
        """Test that email is sent to organization when setting is true"""
        user = UserFactory(email="user@example.com")
        organization = OrganizationFactory(
            email="org@example.com", send_booking_emails_only_to_organization=True
        )
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_NOT_AVAILABLE,
            subject="Not available",
            body="Not available",
            active=True,
        )
        booking = BookingFactory(
            user=user, organization=organization, status=BookingStatus.UNAVAILABLE
        )

        send_booking_not_available_email.call(booking.id)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["org@example.com"]

    def test_email_includes_booking_details(self):
        """Test that email includes booking details in context"""
        resource = ResourceFactory(name="Meeting Room A")
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=2)
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_NOT_AVAILABLE,
            subject=(
                "Not available: {{ booking.title }} " "for {{ booking.resource.name }}"
            ),
            body=(
                "Resource: {{ booking.resource.name }}, "
                "Time: {{ booking.timespan.lower }}"
            ),
            active=True,
        )
        booking = BookingFactory(
            title="Important Meeting",
            resource=resource,
            timespan=Range(start, end),
            status=BookingStatus.UNAVAILABLE,
        )

        send_booking_not_available_email.call(booking.id)

        assert len(mail.outbox) == 1
        assert "Important Meeting" in mail.outbox[0].subject
        assert "Meeting Room A" in mail.outbox[0].subject
        assert "Meeting Room A" in mail.outbox[0].body


class SendBookingReminderEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.BOOKING_REMINDER,
            subject="Booking reminder: {{ booking.title }}",
            body="Reminder for {{ booking.title }}",
            active=True,
        )

    def test_sends_reminder_email(self):
        future_time = timezone.now() + timedelta(days=5)
        future_time = future_time.replace(hour=10, minute=0, second=0, microsecond=0)
        booking = BookingFactory(
            title="Future Booking",
            status=BookingStatus.CONFIRMED,
            timespan=Range(future_time, future_time + timedelta(hours=2)),
        )

        result = send_booking_reminder_email.call(booking.id)

        assert len(mail.outbox) == 1
        assert "Booking reminder: Future Booking" in mail.outbox[0].subject
        assert result["booking_slug"] == booking.slug


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

        send_manager_new_booking_email.call(booking.id)

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

        send_booking_series_confirmation_email.call(booking_series.id)

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

        send_booking_series_cancellation_email.call(booking_series.id)

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

        send_manager_new_booking_series_email.call(booking_series.id)

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

        organization_confirmation_email.call(organization.id)

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

        organization_confirmation_email.call(organization.id)

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

        organization_cancellation_email.call(organization.id)

        assert len(mail.outbox) == 1
        assert "Organization cancelled" in mail.outbox[0].subject


class SendMonthlyOverviewEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.MONTHLY_BOOKINGS,
            subject="Monthly bookings overview",
            body="Your monthly bookings: {% for booking in bookings %}"
            "{{ booking.title }}{% endfor %}",
            active=True,
        )

    def test_sends_monthly_overview_email(self):
        organization = OrganizationFactory(
            email="org@example.com", monthly_bulk_access_codes=True
        )
        next_month = timezone.now() + timedelta(days=35)
        booking = BookingFactory(
            organization=organization,
            status=BookingStatus.CONFIRMED,
            timespan=Range(
                next_month,
                next_month + timedelta(hours=2),
            ),
            title="Next Month Booking",
        )

        result = send_monthly_overview_email.call(
            organization.id,
            [booking.id],
            next_month.isoformat(),
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["org@example.com"]
        assert result["organization"] == organization.name
        assert result["booking_count"] == 1


class SendCustomOrganizationEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        from re_sharing.organizations.models import Organization

        self.org1 = OrganizationFactory(
            name="Org 1",
            email="org1@example.com",
            status=Organization.Status.CONFIRMED,
        )
        self.org2 = OrganizationFactory(
            name="Org 2",
            email="org2@example.com",
            status=Organization.Status.CONFIRMED,
        )

    def test_sends_email_to_all_organizations(self):
        organizations = [self.org1, self.org2]
        subject = "Test Subject"
        body = "Test Body"

        result = send_custom_organization_email(
            organizations=organizations,
            subject_template=subject,
            body_template=body,
        )

        assert len(mail.outbox) == 2  # noqa: PLR2004
        assert result["sent_count"] == 2  # noqa: PLR2004
        assert "Org 1" in result["sent_organizations"]
        assert "Org 2" in result["sent_organizations"]

    def test_renders_organization_template_tags(self):
        organizations = [self.org1]
        subject = "Hello {{ organization.name }}"
        body = "Your email is {{ organization.email }}"

        send_custom_organization_email(
            organizations=organizations,
            subject_template=subject,
            body_template=body,
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Hello Org 1"
        assert "Your email is org1@example.com" in mail.outbox[0].body

    def test_includes_filter_context_in_templates(self):
        organizations = [self.org1]
        subject = "Test"
        body = "Min bookings: {{ min_bookings }}, Months: {{ months }}"
        filter_context = {"min_bookings": 5, "months": 3}

        send_custom_organization_email(
            organizations=organizations,
            subject_template=subject,
            body_template=body,
            filter_context=filter_context,
        )

        assert len(mail.outbox) == 1
        assert "Min bookings: 5, Months: 3" in mail.outbox[0].body

    def test_includes_booking_count_when_months_in_context(self):
        # Create bookings for org1
        now = timezone.now()
        for _ in range(3):
            BookingFactory(
                organization=self.org1,
                status=BookingStatus.CONFIRMED,
                timespan=Range(now, now + timedelta(hours=1)),
            )

        organizations = [self.org1]
        subject = "Test"
        body = "Bookings: {{ number_of_bookings }}"
        filter_context = {"months": 1}

        send_custom_organization_email(
            organizations=organizations,
            subject_template=subject,
            body_template=body,
            filter_context=filter_context,
        )

        assert len(mail.outbox) == 1
        assert "Bookings: 3" in mail.outbox[0].body

    def test_handles_email_send_failure_gracefully(self):
        organizations = [self.org1, self.org2]
        subject = "Test"
        body = "Test"

        with patch("re_sharing.organizations.mails.EmailMessage.send") as mock_send:
            # First email fails, second succeeds
            mock_send.side_effect = [Exception("Failed"), None]

            result = send_custom_organization_email(
                organizations=organizations,
                subject_template=subject,
                body_template=body,
            )

            # Should still count only successful sends
            assert result["sent_count"] == 1
            assert len(result["sent_organizations"]) == 1

    def test_sends_to_organization_email_address(self):
        organizations = [self.org1]
        subject = "Test"
        body = "Test"

        send_custom_organization_email(
            organizations=organizations,
            subject_template=subject,
            body_template=body,
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["org1@example.com"]

    def test_includes_total_amount_when_months_in_context(self):
        # Create bookings with amounts for org1
        now = timezone.now()
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=Range(now, now + timedelta(hours=1)),
            total_amount=100,
        )
        BookingFactory(
            organization=self.org1,
            status=BookingStatus.CONFIRMED,
            timespan=Range(now, now + timedelta(hours=1)),
            total_amount=150,
        )

        # Get filtered organizations with annotation (only org1 has bookings)
        from re_sharing.organizations.selectors import get_filtered_organizations

        organizations = get_filtered_organizations(months=1, min_bookings=1)

        # Verify we have the right organizations
        assert organizations.count() == 1
        org = organizations.first()
        assert org == self.org1
        assert org.booking_count == 2  # noqa: PLR2004
        assert org.total_amount == 250  # noqa: PLR2004

        subject = "Test"
        body = "Total: {{ total_amount }}"
        filter_context = {"months": 1}

        result = send_custom_organization_email(
            organizations=organizations,
            subject_template=subject,
            body_template=body,
            filter_context=filter_context,
        )

        assert result["sent_count"] == 1
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["org1@example.com"]


class SendPermanentCodeCreatedEmailTest(TestCase):
    """Test permanent code created email sending."""

    def setUp(self):
        mail.outbox.clear()
        self.organization = OrganizationFactory(email="org@example.com")
        self.access1 = AccessFactory(name="Main Door")
        self.access2 = AccessFactory(name="Side Door")

        # Import PermanentCodeFactory here to avoid circular imports
        from re_sharing.resources.tests.factories import PermanentCodeFactory

        self.permanent_code = PermanentCodeFactory(
            code="123456",
            organization=self.organization,
            accesses=[self.access1, self.access2],
        )

    def test_sends_permanent_code_created_email(self):
        """Test that permanent code created email is sent when template is active."""
        from re_sharing.organizations.mails import send_permanent_code_created_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_CREATED,
            subject="Permanent code created for {{ organization.name }}",
            body=(
                "Your permanent code is {{ permanent_code.code }}. "
                "Valid from {{ permanent_code.validity_start }}. "
                "Accesses: {{ accesses }}."
            ),
            active=True,
        )

        send_permanent_code_created_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 1
        assert (
            f"Permanent code created for {self.organization.name}"
            in mail.outbox[0].subject
        )
        assert "123456" in mail.outbox[0].body
        assert mail.outbox[0].to == ["org@example.com"]

    def test_does_not_send_email_when_template_inactive(self):
        """Test that no email is sent when template is inactive."""
        from re_sharing.organizations.mails import send_permanent_code_created_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_CREATED,
            active=False,
        )

        send_permanent_code_created_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 0

    def test_does_not_send_email_when_template_does_not_exist(self):
        """Test that no email is sent when template does not exist."""
        from re_sharing.organizations.mails import send_permanent_code_created_email

        send_permanent_code_created_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 0

    def test_includes_access_names_in_context(self):
        """Test that access names are available in the email context."""
        from re_sharing.organizations.mails import send_permanent_code_created_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_CREATED,
            subject="Permanent code",
            body="Accesses: {{ accesses }}",
            active=True,
        )

        send_permanent_code_created_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 1
        assert "Main Door" in mail.outbox[0].body
        assert "Side Door" in mail.outbox[0].body


class SendPermanentCodeRenewedEmailTest(TestCase):
    """Test permanent code renewed email sending."""

    def setUp(self):
        mail.outbox.clear()
        self.organization = OrganizationFactory(email="org@example.com")
        self.access1 = AccessFactory(name="Main Door")

        # Import PermanentCodeFactory here to avoid circular imports
        from re_sharing.resources.tests.factories import PermanentCodeFactory

        self.old_code = PermanentCodeFactory(
            code="111111",
            organization=self.organization,
            validity_end=timezone.now() + timedelta(weeks=1),
            accesses=[self.access1],
        )
        self.new_code = PermanentCodeFactory(
            code="222222",
            organization=self.organization,
            validity_end=None,
            accesses=[self.access1],
        )

    def test_sends_permanent_code_renewed_email(self):
        """Test that permanent code renewed email is sent when template is active."""
        from re_sharing.organizations.mails import send_permanent_code_renewed_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_RENEWED,
            subject="Permanent code renewed for {{ organization.name }}",
            body=(
                "Your new permanent code is {{ new_code.code }}. "
                "Old code {{ old_code.code }} expires {{ old_code.validity_end }}. "
                "Accesses: {{ accesses }}."
            ),
            active=True,
        )

        send_permanent_code_renewed_email.call(self.new_code.id, self.old_code.id)

        assert len(mail.outbox) == 1
        assert "Permanent code renewed for" in mail.outbox[0].subject
        assert "222222" in mail.outbox[0].body  # new code
        assert "111111" in mail.outbox[0].body  # old code
        assert mail.outbox[0].to == ["org@example.com"]

    def test_does_not_send_email_when_template_inactive(self):
        """Test that no email is sent when template is inactive."""
        from re_sharing.organizations.mails import send_permanent_code_renewed_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_RENEWED,
            active=False,
        )

        send_permanent_code_renewed_email.call(self.new_code.id, self.old_code.id)

        assert len(mail.outbox) == 0

    def test_does_not_send_email_when_template_does_not_exist(self):
        """Test that no email is sent when template does not exist."""
        from re_sharing.organizations.mails import send_permanent_code_renewed_email

        send_permanent_code_renewed_email.call(self.new_code.id, self.old_code.id)

        assert len(mail.outbox) == 0

    def test_includes_both_codes_in_context(self):
        """Test that both old and new codes are available in the email context."""
        from re_sharing.organizations.mails import send_permanent_code_renewed_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_RENEWED,
            subject="Code renewed",
            body=(
                "New: {{ new_code.code }}, "
                "Old: {{ old_code.code }}, "
                "Expires: {{ old_code.validity_end }}"
            ),
            active=True,
        )

        send_permanent_code_renewed_email.call(self.new_code.id, self.old_code.id)

        assert len(mail.outbox) == 1
        assert "New: 222222" in mail.outbox[0].body
        assert "Old: 111111" in mail.outbox[0].body
        assert "Expires:" in mail.outbox[0].body


class SendPermanentCodeInvalidatedEmailTest(TestCase):
    """Test permanent code invalidated email sending."""

    def setUp(self):
        mail.outbox.clear()
        self.organization = OrganizationFactory(email="org@example.com")
        self.access1 = AccessFactory(name="Main Door")

        # Import PermanentCodeFactory here to avoid circular imports
        from re_sharing.resources.tests.factories import PermanentCodeFactory

        self.permanent_code = PermanentCodeFactory(
            code="123456",
            organization=self.organization,
            validity_end=timezone.now() + timedelta(days=7),
            accesses=[self.access1],
        )

    def test_sends_permanent_code_invalidated_email(self):
        """Test that permanent code invalidated email is sent."""
        from re_sharing.organizations.mails import send_permanent_code_invalidated_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_INVALIDATED,
            subject="Permanent code invalidated for {{ organization.name }}",
            body=(
                "Your permanent code {{ permanent_code.code }} "
                "will expire on {{ validity_end }}."
            ),
            active=True,
        )

        send_permanent_code_invalidated_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 1
        assert (
            f"Permanent code invalidated for {self.organization.name}"
            in mail.outbox[0].subject
        )
        assert "123456" in mail.outbox[0].body
        assert mail.outbox[0].to == ["org@example.com"]

    def test_does_not_send_email_when_template_inactive(self):
        """Test that no email is sent when template is inactive."""
        from re_sharing.organizations.mails import send_permanent_code_invalidated_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_INVALIDATED,
            active=False,
        )

        send_permanent_code_invalidated_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 0

    def test_does_not_send_email_when_template_does_not_exist(self):
        """Test that no email is sent when template does not exist."""
        from re_sharing.organizations.mails import send_permanent_code_invalidated_email

        send_permanent_code_invalidated_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 0

    def test_includes_validity_end_in_context(self):
        """Test that validity_end is available in the email context."""
        from re_sharing.organizations.mails import send_permanent_code_invalidated_email

        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.PERMANENT_CODE_INVALIDATED,
            subject="Code invalidated",
            body="Code {{ permanent_code.code }} expires {{ validity_end }}",
            active=True,
        )

        send_permanent_code_invalidated_email.call(self.permanent_code.id)

        assert len(mail.outbox) == 1
        assert "123456" in mail.outbox[0].body
        # validity_end should be in the body
        assert "expires" in mail.outbox[0].body.lower()
