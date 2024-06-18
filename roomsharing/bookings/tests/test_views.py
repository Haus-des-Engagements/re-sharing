import datetime
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.views import list_bookings_view
from roomsharing.organizations.models import Membership
from roomsharing.organizations.tests.factories import MembershipFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.users.tests.factories import UserFactory


class TestListBookingsView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()

    def test_authenticated(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse("bookings:list-bookings"))
        assert response.status_code == HTTPStatus.OK

    def test_not_authenticated(self):
        request = self.factory.get("/bookings/")
        request.user = AnonymousUser()
        response = list_bookings_view(request)
        login_url = reverse(settings.LOGIN_URL)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"{login_url}?next=/bookings/"

    def test_get_only_own_organization_bookings(self):
        client = Client()
        client.force_login(self.user)

        o1 = OrganizationFactory()
        MembershipFactory(
            organization=o1, user=self.user, status=Membership.Status.CONFIRMED
        )
        total_bookings_for_o1 = 2
        r1 = RoomFactory()
        r2 = RoomFactory()

        tomorrow = timezone.now() + datetime.timedelta(days=1)
        start_time = make_aware(
            datetime.datetime.combine(tomorrow, datetime.time(15, 0)),
        )
        end_time = make_aware(datetime.datetime.combine(tomorrow, datetime.time(16, 0)))
        BookingFactory(organization=o1, timespan=(start_time, end_time), room=r1)
        BookingFactory(organization=o1, timespan=(start_time, end_time), room=r2)

        client.login(username=self.user.email, password=self.user.password)
        response = client.get(reverse("bookings:list-bookings"))

        assert response.status_code == HTTPStatus.OK
        assert len(list(response.context["bookings"])) == total_bookings_for_o1

        form = response.context.get("form")
        assert form is not None
