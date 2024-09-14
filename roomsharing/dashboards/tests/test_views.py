from http import HTTPStatus

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.dashboards.views import users_bookings_and_permissions_dashboard_view
from roomsharing.users.tests.factories import UserFactory


class TestListBookingsView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()

    def test_authenticated(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse("dashboards:users_bookings_and_permissions"))
        assert response.status_code == HTTPStatus.OK

    def test_not_authenticated(self):
        request = self.factory.get("/dashboard/")
        request.user = AnonymousUser()
        response = users_bookings_and_permissions_dashboard_view(request)
        login_url = reverse(settings.LOGIN_URL)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"{login_url}?next=/dashboard/"
