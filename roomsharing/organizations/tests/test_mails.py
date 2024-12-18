from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from roomsharing.organizations.mails import booking_cancellation_email
from roomsharing.organizations.mails import booking_confirmation_email
from roomsharing.organizations.mails import booking_reminder_email
from roomsharing.organizations.mails import get_recipient_booking
from roomsharing.organizations.mails import get_recipient_rrule
from roomsharing.organizations.mails import manager_new_booking
from roomsharing.organizations.mails import manager_new_recurrence
from roomsharing.organizations.mails import organization_cancellation_email
from roomsharing.organizations.mails import organization_confirmation_email
from roomsharing.organizations.mails import recurrence_cancellation_email
from roomsharing.organizations.mails import recurrence_confirmation_email


class BookingConfirmationEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    @patch("roomsharing.organizations.mails.get_access_code")
    @patch("roomsharing.organizations.mails.timezone.now")
    @patch("roomsharing.organizations.mails.booking_ics")
    def test_booking_confirmation_email(  # noqa: PLR0913
        self,
        mock_booking_ics,
        mock_timezone_now,
        mock_get_access_code,
        mock_site,
        mock_email_template,
        mock_email_message,
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.BOOKING_CONFIRMATION = (
            "booking_confirmation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance
        mock_get_access_code.return_value = "123456"

        mock_booking = MagicMock()
        mock_booking.uuid = "123-uuid"
        mock_booking.title = "Test Booking"
        mock_booking.timespan.lower = timezone.now()
        mock_booking.timespan.upper = timezone.now() + timezone.timedelta(hours=1)
        mock_booking.room.name = "Test Room"
        mock_booking.room.address = "123 Test St"
        mock_booking.room.slug = "test-room"
        mock_booking.organization.slug = "test-org"
        mock_booking.get_absolute_url.return_value = "/booking/123-url"
        mock_booking.user.email = "user@example.com"
        mock_booking.slug = "test-booking"
        mock_timezone_now.return_value = timezone.now()
        mock_booking_ics.return_value = "ICS_CONTENT"

        booking_confirmation_email(mock_booking)

        mock_site.objects.get_current.assert_called_once()
        mock_get_access_code.assert_called_once_with(
            "test-room", "test-org", mock_booking.timespan.lower
        )
        mock_email_template.objects.get.assert_called_once_with(
            email_type="booking_confirmation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_booking(mock_booking),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.attach.assert_called_once_with(
            "booking_test-booking.ics", "ICS_CONTENT", "text/calendar"
        )
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class BookingCancellationEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    @patch("roomsharing.organizations.mails.get_access_code")
    @patch("roomsharing.organizations.mails.timezone.now")
    def test_booking_cancellation_email(  # noqa: PLR0913
        self,
        mock_timezone_now,
        mock_get_access_code,
        mock_site,
        mock_email_template,
        mock_email_message,
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.BOOKING_CANCELLATION = (
            "booking_cancellation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance
        mock_get_access_code.return_value = "123456"

        mock_booking = MagicMock()
        mock_booking.user.email = "user@example.com"

        booking_cancellation_email(mock_booking)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="booking_cancellation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_booking(mock_booking),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class BookingReminderEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    @patch("roomsharing.organizations.mails.get_access_code")
    @patch("roomsharing.organizations.mails.timezone.now")
    @patch("roomsharing.organizations.mails.booking_ics")
    def test_booking_reminder_email(  # noqa: PLR0913
        self,
        mock_booking_ics,
        mock_timezone_now,
        mock_get_access_code,
        mock_site,
        mock_email_template,
        mock_email_message,
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.BOOKING_REMINDER = "booking_reminder"
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance
        mock_get_access_code.return_value = "123456"
        mock_booking_ics.return_value = "ICS_CONTENT"

        mock_booking = MagicMock()
        mock_booking.room.slug = "test-room"
        mock_booking.organization.slug = "test-org"
        mock_booking.timespan.lower = timezone.now()
        mock_booking.user.email = "user@example.com"
        mock_booking.slug = "test-booking"

        booking_reminder_email(mock_booking)

        mock_site.objects.get_current.assert_called_once()
        mock_get_access_code.assert_called_once_with(
            "test-room", "test-org", mock_booking.timespan.lower
        )
        mock_email_template.objects.get.assert_called_once_with(
            email_type="booking_reminder"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_booking(mock_booking),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.attach.assert_called_once_with(
            "booking_test-booking.ics", "ICS_CONTENT", "text/calendar"
        )
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class ManagerNewBookingTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    def test_manager_new_booking(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.MANAGER_NEW_BOOKING = "manager_new_booking"
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_booking = MagicMock()

        manager_new_booking(mock_booking)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="manager_new_booking"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_MANAGER_EMAIL],
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class RecurrenceConfirmationEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    def test_recurrence_confirmation_email(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.RECURRENCE_CONFIRMATION = (
            "recurrence_confirmation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_rrule = MagicMock()

        recurrence_confirmation_email(mock_rrule)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="recurrence_confirmation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_rrule(mock_rrule),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class RecurrenceCancellationEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    def test_recurrence_cancellation_email(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.RECURRENCE_CANCELLATION = (
            "recurrence_cancellation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_rrule = MagicMock()

        recurrence_cancellation_email(mock_rrule)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="recurrence_cancellation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_rrule(mock_rrule),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class ManagerNewRecurrenceTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    def test_manager_new_recurrence(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.MANAGER_NEW_RECURRENCE = (
            "manager_new_recurrence"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_rrule = MagicMock()
        mock_rrule.get_first_booking.return_value.user.email = "user@example.com"

        manager_new_recurrence(mock_rrule)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="manager_new_recurrence"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_MANAGER_EMAIL],
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class OrganizationConfirmationEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    def test_organization_confirmation_email(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.ORGANIZATION_CONFIRMATION = (
            "organization_confirmation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_organization = MagicMock()
        mock_organization.get_confirmed_admins.return_value.values_list.return_value = [
            "admin1@example.com"
        ]
        mock_organization.email = "org@example.com"

        organization_confirmation_email(mock_organization)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="organization_confirmation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            ["admin1@example.com", "org@example.com"],
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class OrganizationCancellationEmailTestCase(TestCase):
    @patch("roomsharing.organizations.mails.EmailMessage")
    @patch("roomsharing.organizations.mails.EmailTemplate")
    @patch("roomsharing.organizations.mails.Site")
    def test_organization_cancellation_email(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.ORGANIZATION_CANCELLATION = (
            "organization_cancellation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance
        mock_organization = MagicMock()
        mock_organization.get_confirmed_admins.return_value.values_list.return_value = [
            "admin1@example.com"
        ]
        mock_organization.email = "org@example.com"

        organization_cancellation_email(mock_organization)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="organization_cancellation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            ["admin1@example.com", "org@example.com"],
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)
