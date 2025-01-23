from unittest import skip
from unittest.mock import MagicMock
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from re_sharing.organizations.mails import booking_cancellation_email
from re_sharing.organizations.mails import booking_confirmation_email
from re_sharing.organizations.mails import booking_reminder_email
from re_sharing.organizations.mails import booking_series_cancellation_email
from re_sharing.organizations.mails import booking_series_confirmation_email
from re_sharing.organizations.mails import get_recipient_booking
from re_sharing.organizations.mails import get_recipient_booking_series
from re_sharing.organizations.mails import manager_new_booking
from re_sharing.organizations.mails import manager_new_booking_series_email
from re_sharing.organizations.mails import organization_cancellation_email
from re_sharing.organizations.mails import organization_confirmation_email


class BookingConfirmationEmailTestCase(TestCase):
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
    @patch("re_sharing.organizations.mails.get_access_code")
    @patch("re_sharing.organizations.mails.timezone.now")
    @patch("re_sharing.organizations.mails.booking_ics")
    @skip("Temporarily disabled for debugging")
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
        mock_booking.resource.name = "Test Resource"
        mock_booking.resource.address = "123 Test St"
        mock_booking.resource.slug = "test-resource"
        mock_booking.organization.slug = "test-org"
        mock_booking.get_absolute_url.return_value = "/booking/123-url"
        mock_booking.user.email = "user@example.com"
        mock_booking.slug = "test-booking"
        mock_timezone_now.return_value = timezone.now()
        mock_booking_ics.return_value = "ICS_CONTENT"

        booking_confirmation_email(mock_booking)

        mock_site.objects.get_current.assert_called_once()
        mock_get_access_code.assert_called_once_with(
            "test-resource", "test-org", mock_booking.timespan.lower
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
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
    @patch("re_sharing.organizations.mails.get_access_code")
    @patch("re_sharing.organizations.mails.timezone.now")
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
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
    @patch("re_sharing.organizations.mails.get_access_code")
    @patch("re_sharing.organizations.mails.timezone.now")
    @patch("re_sharing.organizations.mails.booking_ics")
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
        mock_booking.resource.slug = "test-resource"
        mock_booking.organization.slug = "test-org"
        mock_booking.timespan.lower = timezone.now()
        mock_booking.user.email = "user@example.com"
        mock_booking.slug = "test-booking"

        booking_reminder_email(mock_booking)

        mock_site.objects.get_current.assert_called_once()
        mock_get_access_code.assert_called_once_with(
            "test-resource", "test-org", mock_booking.timespan.lower
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
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
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


class BookingSeriesConfirmationEmailTestCase(TestCase):
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
    def test_booking_series_confirmation_email(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.BOOKING_SERIES_CONFIRMATION = (
            "booking_series_confirmation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_rrule = MagicMock()

        booking_series_confirmation_email(mock_rrule)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="booking_series_confirmation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_booking_series(mock_rrule),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class BookingSeriesCancellationEmailTestCase(TestCase):
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
    def test_booking_series_cancellation_email(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.BOOKING_SERIES_CANCELLATION = (
            "booking_series_cancellation"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_rrule = MagicMock()

        booking_series_cancellation_email(mock_rrule)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="booking_series_cancellation"
        )
        mock_email_message.assert_called_once_with(
            "Test Subject",
            "Test Body",
            settings.DEFAULT_FROM_EMAIL,
            get_recipient_booking_series(mock_rrule),
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class ManagerNewBookingSeriesTestCase(TestCase):
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
    def test_manager_new_booking_series(
        self, mock_site, mock_email_template, mock_email_message
    ):
        mock_site.objects.get_current.return_value.domain = "example.com"
        mock_email_template.EmailTypeChoices.MANAGER_NEW_BOOKING_SERIES = (
            "manager_new_booking_series"
        )
        email_template_instance = MagicMock()
        email_template_instance.subject = "Test Subject"
        email_template_instance.body = "Test Body"
        mock_email_template.objects.get.return_value = email_template_instance

        mock_rrule = MagicMock()
        mock_rrule.get_first_booking.return_value.user.email = "user@example.com"

        manager_new_booking_series_email(mock_rrule)

        mock_site.objects.get_current.assert_called_once()
        mock_email_template.objects.get.assert_called_once_with(
            email_type="manager_new_booking_series"
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
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
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
            ["admin1@example.com"],
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)


class OrganizationCancellationEmailTestCase(TestCase):
    @patch("re_sharing.organizations.mails.EmailMessage")
    @patch("re_sharing.organizations.mails.EmailTemplate")
    @patch("re_sharing.organizations.mails.Site")
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
            ["admin1@example.com"],
        )
        mock_email_instance = mock_email_message.return_value
        mock_email_instance.send.assert_called_once_with(fail_silently=False)
