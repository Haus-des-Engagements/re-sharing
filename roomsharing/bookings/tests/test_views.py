import datetime
from http import HTTPStatus
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from config.settings.base import ADMIN_URL
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.tests.factories import BookingMessageFactory
from roomsharing.bookings.views import list_bookings_view
from roomsharing.bookings.views import manager_list_bookings_view
from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.tests.factories import BookingPermissionFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.users.tests.factories import UserFactory
from roomsharing.utils.models import BookingStatus


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
        BookingPermissionFactory(
            organization=o1, user=self.user, status=BookingPermission.Status.CONFIRMED
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


class TestShowBookingView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.booking = BookingFactory(organization=self.organization)
        self.show_booking_url = reverse(
            "bookings:show-booking",
            kwargs={"booking": self.booking.slug},
        )

    def test_no_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.PENDING,
        )
        client = Client()
        client.force_login(self.user)
        response = client.get(self.show_booking_url)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_has_booking_permission(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        client = Client()
        client.force_login(self.user)
        response = client.get(self.show_booking_url)
        assert response.status_code == HTTPStatus.OK

    def test_activity_stream(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        message1 = BookingMessageFactory(booking=self.booking, user=self.user)
        message2 = BookingMessageFactory(booking=self.booking, user=self.user)
        self.booking.status = BookingStatus.CONFIRMED
        self.booking.status = BookingStatus.CANCELLED
        client = Client()
        client.force_login(self.user)
        response = client.get(self.show_booking_url)
        self.assertContains(response, message1.text)
        self.assertContains(response, message2.text)

        assert response.status_code == HTTPStatus.OK


class TestManagerBookingsView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory(is_staff=True)

    def test_authenticated(self):
        client = Client()
        client.force_login(self.user)
        response = client.get(reverse("bookings:manager-list-bookings"))
        assert response.status_code == HTTPStatus.OK

    def test_not_authenticated(self):
        request = self.factory.get("/manage-bookings/")
        request.user = AnonymousUser()
        response = manager_list_bookings_view(request)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"/{ADMIN_URL}login/?next=/manage-bookings/"


class TestManagerActionsBookingView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = UserFactory(is_staff=True)
        self.user = UserFactory(is_staff=False)
        self.booking = BookingFactory()
        self.cancel_booking_url = reverse(
            "bookings:manager-cancel-booking",
            kwargs={"booking_slug": self.booking.slug},
        )
        self.confirm_booking_url = reverse(
            "bookings:manager-confirm-booking",
            kwargs={"booking_slug": self.booking.slug},
        )

    @patch("roomsharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_staff(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.staff_user)

        response = client.get(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("roomsharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_non_staff(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.get(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/{ADMIN_URL}login/?next=/bookings/manage-bookings/{self.booking.slug}"
            f"/cancel-booking/"
        )

    @patch("roomsharing.bookings.models.Booking.is_confirmable", return_value=True)
    def test_confirm_by_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.staff_user)

        response = client.get(self.confirm_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("roomsharing.bookings.models.Booking.is_confirmable", return_value=True)
    def test_confirm_by_non_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.user)

        response = client.get(self.confirm_booking_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/{ADMIN_URL}login/?next=/bookings/manage-bookings/{self.booking.slug}"
            f"/confirm-booking/"
        )


class TestCancelBookingView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking = BookingFactory(organization=self.organization)
        self.cancel_booking_url = reverse(
            "bookings:cancel-booking",
            kwargs={"slug": self.booking.slug},
        )

    @patch("roomsharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.get(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("roomsharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_not_logged_in_user(self, mock_is_cancelable):
        client = Client()

        response = client.get(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/accounts/login/?next=/bookings/{self.booking.slug}/cancel-booking/"
        )


class TestCancelOccurrenceView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking = BookingFactory(organization=self.organization)
        self.cancel_occurrence_url = reverse(
            "bookings:cancel-occurrence",
            kwargs={"slug": self.booking.slug},
        )

    @patch("roomsharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.get(self.cancel_occurrence_url)
        assert response.status_code == HTTPStatus.OK

    @patch("roomsharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_not_logged_in_user(self, mock_is_cancelable):
        client = Client()

        response = client.get(self.cancel_occurrence_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/accounts/login/?next=/bookings/{self.booking.slug}/cancel-occurrence/"
        )
