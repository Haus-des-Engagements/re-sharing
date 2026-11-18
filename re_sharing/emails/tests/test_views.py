from datetime import UTC
from datetime import datetime
from http import HTTPStatus

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape
from freezegun import freeze_time

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.emails.models import EmailLog
from re_sharing.emails.tests.factories import EmailLogFactory
from re_sharing.emails.tests.helpers import with_email_log
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.users.tests.factories import UserFactory


class ManagerViewTestCase(TestCase):
    def setUp(self):
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.client.force_login(self.manager_user)
        self.list_url = reverse("emails:list-emails")

    def _subjects(self, response):
        return [entry.subject for entry in response.context["page"]]


class ListEmailsViewTest(ManagerViewTestCase):
    def test_lists_emails_newest_first(self):
        EmailLogFactory(subject="Older", to=["old@example.org"])
        EmailLogFactory(subject="Newer", email_type="custom")

        response = self.client.get(self.list_url)

        assert response.status_code == HTTPStatus.OK
        assert self._subjects(response) == ["Newer", "Older"]
        content = response.content.decode()
        assert "old@example.org" in content
        assert "custom" in content

    def test_empty_log(self):
        response = self.client.get(self.list_url)

        assert "No emails found." in response.content.decode()
        assert "Send selected again" not in response.content.decode()

    def test_fifty_per_page_and_page_links_keep_the_filters(self):
        for number in range(60):
            EmailLogFactory(subject=f"Email {number}", email_type="custom")
        EmailLogFactory(subject="Other type", email_type="other")

        first = self.client.get(self.list_url, {"email_type": "custom"})

        assert len(first.context["page"]) == 50  # noqa: PLR2004
        assert self._subjects(first)[0] == "Email 59"
        content = first.content.decode()
        assert "Page 1 of 2" in content
        assert "?email_type=custom&amp;page=2" in content

        second = self.client.get(self.list_url, {"email_type": "custom", "page": 2})

        assert len(second.context["page"]) == 10  # noqa: PLR2004
        assert self._subjects(second)[-1] == "Email 0"
        assert "?email_type=custom&amp;page=1" in second.content.decode()

    def test_single_page_has_no_page_links(self):
        EmailLogFactory()

        response = self.client.get(self.list_url)

        assert "Page 1 of" not in response.content.decode()

    def test_filter_by_status(self):
        EmailLogFactory(subject="Accepted")
        EmailLogFactory(subject="Rejected", status=EmailLog.Status.FAILED)

        response = self.client.get(self.list_url, {"status": "failed"})

        assert self._subjects(response) == ["Rejected"]

    def test_search_by_recipient_and_subject(self):
        EmailLogFactory(subject="First", to=["anna@example.org"])
        EmailLogFactory(subject="Second", to=["x@example.org"], cc=["anna@example.org"])
        EmailLogFactory(subject="Third about Anna", to=["y@example.org"])
        EmailLogFactory(subject="Fourth", to=["z@example.org"])

        response = self.client.get(self.list_url, {"search": "anna"})

        assert set(self._subjects(response)) == {"First", "Second", "Third about Anna"}

    def test_filter_by_organization(self):
        organization = OrganizationFactory()
        EmailLogFactory(subject="Theirs", organization=organization)
        EmailLogFactory(subject="Other", organization=OrganizationFactory())
        EmailLogFactory(subject="None")

        response = self.client.get(self.list_url, {"organization": organization.pk})

        assert self._subjects(response) == ["Theirs"]
        assert escape(organization.name) in response.content.decode()

    def test_filter_by_type(self):
        EmailLogFactory(subject="Custom", email_type="custom")
        EmailLogFactory(subject="Booking", email_type="booking_confirmation")

        response = self.client.get(self.list_url, {"email_type": "custom"})

        assert self._subjects(response) == ["Custom"]

    def test_filter_by_date_range(self):
        for day in (10, 11, 12, 13):
            with freeze_time(datetime(2026, 11, day, 12, tzinfo=UTC)):
                EmailLogFactory(subject=f"Day {day}")

        response = self.client.get(
            self.list_url, {"from_date": "2026-11-11", "to_date": "2026-11-12"}
        )

        assert self._subjects(response) == ["Day 12", "Day 11"]

    def test_invalid_filter_value_is_ignored(self):
        EmailLogFactory(subject="Accepted")

        response = self.client.get(
            self.list_url, {"from_date": "not a date", "status": "sent"}
        )

        assert self._subjects(response) == ["Accepted"]

    def test_not_a_manager(self):
        self.client.force_login(UserFactory())

        assert self.client.get(self.list_url).status_code == HTTPStatus.FORBIDDEN

    def test_navigation_links_to_the_log(self):
        response = self.client.get(self.list_url)

        assert f'href="{self.list_url}"' in response.content.decode()


class ShowEmailViewTest(ManagerViewTestCase):
    def test_shows_the_email_as_sent(self):
        booking = BookingFactory()
        entry = EmailLogFactory(
            subject="Your booking",
            to=["a@example.org", "b@example.org"],
            cc=["cc@example.org"],
            bcc=["bcc@example.org"],
            body_text="Plain content",
            body_html="<p>Formatted <b>content</b></p>",
            email_type="booking_confirmation",
            booking=booking,
            organization=booking.organization,
            user=booking.user,
        )

        response = self.client.get(entry.get_absolute_url())

        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        assert "Your booking" in content
        assert "a@example.org, b@example.org" in content
        assert "cc@example.org" in content
        assert "bcc@example.org" in content
        assert "Plain content" in content
        assert "booking_confirmation" in content
        assert escape(booking.organization.name) in content
        assert booking.get_absolute_url() in content
        # the HTML is escaped into a sandboxed frame, never part of the page
        assert 'sandbox=""' in content
        assert "&lt;p&gt;Formatted &lt;b&gt;content&lt;/b&gt;&lt;/p&gt;" in content
        assert "<p>Formatted" not in content
        assert "Send again" in content

    def test_failed_email_shows_the_error(self):
        entry = EmailLogFactory(
            status=EmailLog.Status.FAILED, error="550 Mailbox unavailable"
        )

        content = self.client.get(entry.get_absolute_url()).content.decode()

        assert "550 Mailbox unavailable" in content
        assert "did not accept this email" in content

    def test_sent_email_warns_about_a_second_delivery(self):
        entry = EmailLogFactory()

        content = self.client.get(entry.get_absolute_url()).content.decode()

        assert "get it a second time" in content
        assert "without its attachments" not in content

    def test_attachments_are_named_and_not_sent_again(self):
        entry = EmailLogFactory(attachment_names=["booking.ics"])

        content = self.client.get(entry.get_absolute_url()).content.decode()

        assert "booking.ics" in content
        assert "without its attachments" in content

    def test_unknown_entry(self):
        url = reverse("emails:show-email", kwargs={"pk": 999999})

        assert self.client.get(url).status_code == HTTPStatus.NOT_FOUND

    def test_not_a_manager(self):
        entry = EmailLogFactory()
        self.client.force_login(UserFactory())

        response = self.client.get(entry.get_absolute_url())

        assert response.status_code == HTTPStatus.FORBIDDEN


@with_email_log
class ResendEmailViewsTest(ManagerViewTestCase):
    def setUp(self):
        super().setUp()
        self.resend_selected_url = reverse("emails:resend-selected-emails")

    def _resend_url(self, entry):
        return reverse("emails:resend-email", kwargs={"pk": entry.pk})

    def test_failed_email_is_retried_on_its_entry(self):
        entry = EmailLogFactory(status=EmailLog.Status.FAILED, error="550")

        response = self.client.post(self._resend_url(entry), follow=True)

        self.assertRedirects(response, entry.get_absolute_url())
        assert "1 email is scheduled to be sent again." in response.content.decode()
        assert len(mail.outbox) == 1
        entry = EmailLog.objects.get()
        assert entry.status == EmailLog.Status.SENT
        assert entry.attempts == 2  # noqa: PLR2004

    def test_sent_email_is_sent_as_a_new_entry(self):
        entry = EmailLogFactory(subject="Again")

        self.client.post(self._resend_url(entry))

        assert len(mail.outbox) == 1
        assert EmailLog.objects.filter(subject="Again").count() == 2  # noqa: PLR2004

    def test_resend_needs_post(self):
        entry = EmailLogFactory()

        response = self.client.get(self._resend_url(entry))

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert len(mail.outbox) == 0

    def test_several_selected_emails(self):
        failed = EmailLogFactory(status=EmailLog.Status.FAILED, error="550")
        sent = EmailLogFactory()
        untouched = EmailLogFactory(subject="Untouched")

        response = self.client.post(
            self.resend_selected_url,
            {"selected": [failed.pk, sent.pk, "not-a-number"]},
            follow=True,
        )

        self.assertRedirects(response, self.list_url)
        assert "2 emails are scheduled to be sent again." in response.content.decode()
        assert len(mail.outbox) == 2  # noqa: PLR2004
        failed.refresh_from_db()
        assert failed.status == EmailLog.Status.SENT
        assert EmailLog.objects.count() == 4  # noqa: PLR2004
        assert EmailLog.objects.filter(subject="Untouched").count() == 1
        assert untouched.attempts == 1

    def test_nothing_selected(self):
        EmailLogFactory()

        response = self.client.post(self.resend_selected_url, follow=True)

        assert "Please select at least one email." in response.content.decode()
        assert len(mail.outbox) == 0

    def test_not_a_manager(self):
        entry = EmailLogFactory()
        self.client.force_login(UserFactory())

        single = self.client.post(self._resend_url(entry))
        several = self.client.post(self.resend_selected_url, {"selected": [entry.pk]})

        assert single.status_code == HTTPStatus.FORBIDDEN
        assert several.status_code == HTTPStatus.FORBIDDEN
        assert len(mail.outbox) == 0
