from django.test import TestCase

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.emails.models import EmailLog
from re_sharing.emails.tests.factories import EmailLogFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.users.tests.factories import UserFactory


class EmailLogTest(TestCase):
    def test_defaults(self):
        entry = EmailLog.objects.create()

        assert entry.status == EmailLog.Status.FAILED
        assert entry.to == []
        assert entry.attachment_names == []
        assert entry.attempts == 0
        assert entry.sent_at is None
        assert entry.created is not None

    def test_entry_survives_the_deletion_of_its_links(self):
        booking = BookingFactory()
        organization = OrganizationFactory()
        user = UserFactory()
        entry = EmailLogFactory(booking=booking, organization=organization, user=user)

        booking.delete()
        organization.delete()
        user.delete()

        entry.refresh_from_db()
        assert entry.booking is None
        assert entry.organization is None
        assert entry.user is None

    def test_newest_first(self):
        older = EmailLogFactory()
        newer = EmailLogFactory()

        assert list(EmailLog.objects.all()) == [newer, older]

    def test_text_representation_and_recipients(self):
        entry = EmailLogFactory(to=["a@example.org", "b@example.org"], subject="Hello")

        assert entry.recipients_display == "a@example.org, b@example.org"
        assert str(entry) == "a@example.org, b@example.org: Hello"
        assert entry.get_absolute_url() == f"/emails/{entry.pk}/"
