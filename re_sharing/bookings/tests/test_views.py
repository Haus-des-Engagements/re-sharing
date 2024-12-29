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
from re_sharing.bookings.forms import BookingForm
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingMessageFactory
from re_sharing.bookings.tests.factories import RecurrenceRuleFactory
from re_sharing.bookings.views import list_bookings_view
from re_sharing.bookings.views import manager_list_bookings_view
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.tests.factories import RoomFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


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

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_staff(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.staff_user)

        response = client.patch(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_non_staff(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/{ADMIN_URL}login/?next=/bookings/manage-bookings/{self.booking.slug}"
            f"/cancel-booking/"
        )

    @patch("re_sharing.bookings.models.Booking.is_confirmable", return_value=True)
    def test_confirm_by_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.staff_user)

        response = client.patch(self.confirm_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("re_sharing.bookings.models.Booking.is_confirmable", return_value=True)
    def test_confirm_by_non_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.confirm_booking_url)
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

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_not_logged_in_user(self, mock_is_cancelable):
        client = Client()

        response = client.patch(self.cancel_booking_url)
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

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.cancel_occurrence_url)
        assert response.status_code == HTTPStatus.OK

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_not_logged_in_user(self, mock_is_cancelable):
        client = Client()

        response = client.patch(self.cancel_occurrence_url)
        assert response.status_code == HTTPStatus.FOUND
        assert (
            response.url
            == f"/accounts/login/?next=/bookings/{self.booking.slug}/cancel-occurrence/"
        )


class ListRecurrencesViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_list_recurrences_view(self):
        response = self.client.get(reverse("bookings:list-recurrences"))
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/list_recurrences.html")
        assert "recurrences" in response.context


class ShowRecurrenceView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.rrule = RecurrenceRuleFactory()
        self.booking = BookingFactory(recurrence_rule=self.rrule)

    @patch("re_sharing.bookings.views.get_rrule_bookings")
    def test_show_recurrence_view(self, mock_get_occurrences):
        mock_get_occurrences.return_value = (self.rrule, [self.booking], False)
        response = self.client.get(
            reverse("bookings:show-recurrence", kwargs={"rrule": self.rrule.slug})
        )
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/show_recurrence.html")
        assert "bookings" in response.context
        assert "rrule" in response.context
        assert "is_cancelable" in response.context


class CreateBookingDataFormViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.client.force_login(self.user)

    @patch("re_sharing.bookings.views.set_initial_booking_data")
    def test_get_request(self, mock_set_initial_booking_data):
        mock_set_initial_booking_data.return_value = {}

        response = self.client.get(
            reverse("bookings:create-booking"),
            {
                "startdate": "2023-10-01",
                "starttime": "08:00",
                "endtime": "17:00",
                "room": "101",
            },
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/create-booking.html")
        form_instance = response.context["form"]
        assert isinstance(form_instance, BookingForm)
