from http import HTTPStatus

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.views import MyBookingsListView
from roomsharing.users.tests.factories import OrganizationFactory
from roomsharing.users.tests.factories import UserFactory


class TestMyBookingListView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()

    def test_authenticated(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse("bookings:my_bookings_list"))
        assert response.status_code == HTTPStatus.OK

    def test_not_authenticated(self):
        request = self.factory.get("/bookings/")
        request.user = AnonymousUser()
        response = MyBookingsListView.as_view()(request)
        login_url = reverse(settings.LOGIN_URL)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"{login_url}?next=/bookings/"

    def test_get_only_own_organization_bookings(self):
        client = Client()
        client.force_login(self.user)

        o1 = OrganizationFactory()
        self.user.organizations.set([o1])
        total_bookings_for_o1 = 2
        BookingFactory(organization=o1)
        BookingFactory(organization=o1)

        client.login(username=self.user.email, password=self.user.password)
        response = client.get(reverse("bookings:my_bookings_list"))

        assert response.status_code == HTTPStatus.OK
        assert len(list(response.context["bookings_list"])) == total_bookings_for_o1
