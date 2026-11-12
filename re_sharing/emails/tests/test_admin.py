from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse

from re_sharing.emails.tests.factories import EmailLogFactory
from re_sharing.users.tests.factories import UserFactory


class EmailLogAdminTest(TestCase):
    def setUp(self):
        self.client.force_login(UserFactory(is_staff=True, is_superuser=True))
        self.list_url = reverse("admin:emails_emaillog_changelist")

    def test_list_and_search_by_recipient(self):
        EmailLogFactory(subject="For Anna", to=["anna@example.org"])
        EmailLogFactory(subject="For Ben", to=["ben@example.org"])

        response = self.client.get(self.list_url, {"q": "anna@example.org"})

        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        assert "For Anna" in content
        assert "For Ben" not in content

    def test_entries_cannot_be_added_changed_or_deleted(self):
        entry = EmailLogFactory(subject="Original")
        change_url = reverse("admin:emails_emaillog_change", args=[entry.pk])

        add = self.client.get(reverse("admin:emails_emaillog_add"))
        view = self.client.get(change_url)
        change = self.client.post(change_url, {"subject": "Changed"})
        delete = self.client.post(
            reverse("admin:emails_emaillog_delete", args=[entry.pk]), {"post": "yes"}
        )

        assert add.status_code == HTTPStatus.FORBIDDEN
        assert view.status_code == HTTPStatus.OK
        assert change.status_code == HTTPStatus.FORBIDDEN
        assert delete.status_code == HTTPStatus.FORBIDDEN
        entry.refresh_from_db()
        assert entry.subject == "Original"
