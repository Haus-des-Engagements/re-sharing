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

from re_sharing.bookings.forms import BookingForm
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingMessageFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.bookings.views import list_bookings_view
from re_sharing.bookings.views import manager_list_bookings_view
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.tests.factories import ResourceFactory
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
        r1 = ResourceFactory()
        r2 = ResourceFactory()

        tomorrow = timezone.now() + datetime.timedelta(days=1)
        start_time = make_aware(
            datetime.datetime.combine(tomorrow, datetime.time(15, 0)),
        )
        end_time = make_aware(datetime.datetime.combine(tomorrow, datetime.time(16, 0)))
        BookingFactory(organization=o1, timespan=(start_time, end_time), resource=r1)
        BookingFactory(organization=o1, timespan=(start_time, end_time), resource=r2)

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
        self.user = ManagerFactory().user

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
        assert response.url.endswith("login/?next=/manage-bookings/")


class TestManagerActionsBookingView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.manager = UserFactory()
        ManagerFactory(user=self.manager)
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
    def test_cancel_by_manager(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.manager)

        response = client.patch(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("re_sharing.bookings.models.Booking.is_cancelable", return_value=True)
    def test_cancel_by_non_manager(self, mock_is_cancelable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.cancel_booking_url)
        assert response.status_code == HTTPStatus.FORBIDDEN

    @patch("re_sharing.bookings.models.Booking.is_confirmable", return_value=True)
    def test_confirm_by_staff(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.manager)

        response = client.patch(self.confirm_booking_url)
        assert response.status_code == HTTPStatus.OK

    @patch("re_sharing.bookings.models.Booking.is_confirmable", return_value=True)
    def test_confirm_by_non_manager(self, mock_is_confirmable):
        client = Client()
        client.force_login(self.user)

        response = client.patch(self.confirm_booking_url)
        assert response.status_code == HTTPStatus.FORBIDDEN


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
            "bookings:cancel-booking-series-booking",
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
            response.url == f"/accounts/login/?next=/bookings/{self.booking.slug}/"
            "cancel-booking-series-booking/"
        )


class ListRecurrencesViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_list_recurrences_view(self):
        response = self.client.get(reverse("bookings:list-booking-series"))
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/list_booking_series.html")


class ShowRecurrenceView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.booking_series = BookingSeriesFactory()
        self.booking = BookingFactory(booking_series=self.booking_series)

    @patch("re_sharing.bookings.views.get_bookings_of_booking_series")
    def test_show_recurrence_view(self, mock_get_occurrences):
        mock_get_occurrences.return_value = (self.booking_series, [self.booking], False)
        response = self.client.get(
            reverse(
                "bookings:show-booking-series",
                kwargs={"booking_series": self.booking_series.slug},
            )
        )
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/show_booking_series.html")
        assert "bookings" in response.context
        assert "is_cancelable" in response.context


class CreateBookingDataFormViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
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
                "resource": "101",
            },
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/create-booking.html")
        form_instance = response.context["form"]
        assert isinstance(form_instance, BookingForm)

    @patch("re_sharing.bookings.views.create_booking_data")
    @patch("re_sharing.bookings.forms.BookingForm.is_valid", return_value=True)
    def test_post_request_valid_single_booking(
        self, mock_is_valid, mock_create_booking_data
    ):
        mock_create_booking_data.return_value = (
            {
                "start_date": "2023-10-01",
                "start_time": "08:00",
                "end_time": "17:00",
                "resource": self.resource.id,
                "organization": self.organization.id,
            },
            None,  # No rrule
        )

        response = self.client.post(
            reverse("bookings:create-booking"),
            {"title": "Test Booking"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:preview-booking")

    @patch("re_sharing.bookings.views.create_booking_data")
    @patch("re_sharing.bookings.forms.BookingForm.is_valid", return_value=True)
    def test_post_request_valid_booking_series(
        self, mock_is_valid, mock_create_booking_data
    ):
        mock_create_booking_data.return_value = (
            {
                "start_date": "2023-10-01",
                "start_time": "08:00",
                "end_time": "17:00",
                "resource": self.resource.id,
                "organization": self.organization.id,
            },
            "RRULE:FREQ=WEEKLY;COUNT=5",  # Has rrule
        )

        response = self.client.post(
            reverse("bookings:create-booking"),
            {"title": "Test Recurring Booking"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:preview-booking-series")


class TestPreviewAndSaveBookingView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

    def test_get_without_booking_data_redirects(self):
        response = self.client.get(reverse("bookings:preview-booking"))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:create-booking")

    @patch("re_sharing.bookings.views.generate_booking")
    def test_get_with_booking_data(self, mock_generate_booking):
        booking = BookingFactory.build(
            organization=self.organization, resource=self.resource
        )
        mock_generate_booking.return_value = booking

        session = self.client.session
        session["booking_data"] = {
            "start_date": "2023-10-01",
            "start_time": "08:00",
            "end_time": "17:00",
        }
        session.save()

        response = self.client.get(reverse("bookings:preview-booking"))
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/preview-booking.html")
        assert "booking" in response.context

    @patch("re_sharing.bookings.views.save_booking")
    @patch("re_sharing.bookings.views.generate_booking")
    def test_post_saves_confirmed_booking(
        self, mock_generate_booking, mock_save_booking
    ):
        booking = BookingFactory(
            organization=self.organization,
            resource=self.resource,
            status=BookingStatus.CONFIRMED,
        )
        mock_generate_booking.return_value = booking
        mock_save_booking.return_value = booking

        session = self.client.session
        session["booking_data"] = {"start_date": "2023-10-01"}
        session.save()

        response = self.client.post(reverse("bookings:preview-booking"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:show-booking", args=[booking.slug])
        assert "booking_data" not in self.client.session

    @patch("re_sharing.bookings.views.save_booking")
    @patch("re_sharing.bookings.views.generate_booking")
    def test_post_saves_pending_booking(self, mock_generate_booking, mock_save_booking):
        booking = BookingFactory(
            organization=self.organization,
            resource=self.resource,
            status=BookingStatus.PENDING,
        )
        mock_generate_booking.return_value = booking
        mock_save_booking.return_value = booking

        session = self.client.session
        session["booking_data"] = {"start_date": "2023-10-01"}
        session.save()

        response = self.client.post(reverse("bookings:preview-booking"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:show-booking", args=[booking.slug])


class TestUpdateBookingView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking = BookingFactory(organization=self.organization)
        self.client.force_login(self.user)

    def test_get_with_permission(self):
        response = self.client.get(
            reverse(
                "bookings:update-booking", kwargs={"booking_slug": self.booking.slug}
            )
        )
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/create-booking.html")
        assert "form" in response.context

    def test_get_without_permission(self):
        other_user = UserFactory()
        self.client.force_login(other_user)

        response = self.client.get(
            reverse(
                "bookings:update-booking", kwargs={"booking_slug": self.booking.slug}
            )
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    @patch("re_sharing.bookings.views.create_booking_data")
    @patch("re_sharing.bookings.forms.BookingForm.is_valid", return_value=True)
    def test_post_with_permission(self, mock_is_valid, mock_create_booking_data):
        mock_create_booking_data.return_value = (
            {
                "booking_id": self.booking.id,
                "start_date": "2023-10-01",
                "start_time": "08:00",
                "end_time": "17:00",
            },
            None,
        )

        response = self.client.post(
            reverse(
                "bookings:update-booking", kwargs={"booking_slug": self.booking.slug}
            ),
            {"title": "Updated Booking"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:preview-booking")
        assert "booking_data" in self.client.session


class TestListBookingsViewHTMX(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_htmx_request_returns_partial(self):
        response = self.client.get(
            reverse("bookings:list-bookings"), headers={"hx-request": "true"}
        )
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "list-bookings")


class TestCancelBookingsOfBookingSeriesView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking_series = BookingSeriesFactory(organization=self.organization)
        self.client.force_login(self.user)

    @patch("re_sharing.bookings.views.cancel_bookings_of_booking_series")
    @patch("re_sharing.bookings.views.get_bookings_of_booking_series")
    def test_cancel_booking_series(
        self, mock_get_bookings, mock_cancel_bookings_of_series
    ):
        mock_cancel_bookings_of_series.return_value = self.booking_series
        mock_get_bookings.return_value = (self.booking_series, [], False)

        response = self.client.patch(
            reverse(
                "bookings:cancel-booking-series-bookings",
                kwargs={"booking_series": self.booking_series.uuid},
            )
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/show_booking_series.html")
        mock_cancel_bookings_of_series.assert_called_once()


class TestCreateBookingMessageView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.booking = BookingFactory(organization=self.organization)
        self.client.force_login(self.user)

    @patch("re_sharing.bookings.views.create_bookingmessage")
    def test_create_booking_message(self, mock_create_bookingmessage):
        message = BookingMessageFactory(booking=self.booking, user=self.user)
        mock_create_bookingmessage.return_value = message

        response = self.client.post(
            reverse(
                "bookings:create-bookingmessage", kwargs={"slug": self.booking.slug}
            ),
            {"text": "Test message"},
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/partials/show_bookingmessage.html")
        mock_create_bookingmessage.assert_called_once()


class TestPreviewAndSaveBookingSeriesView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()
        BookingPermissionFactory(
            user=self.user,
            organization=self.organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

    def test_get_without_booking_data_redirects(self):
        response = self.client.get(reverse("bookings:preview-booking-series"))
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("bookings:create-booking")

    @patch("re_sharing.bookings.views.create_booking_series_and_bookings")
    def test_get_with_booking_data(self, mock_create_series):
        booking_series = BookingSeriesFactory.build(
            organization=self.organization, resource=self.resource
        )
        bookings = [BookingFactory.build()]
        mock_create_series.return_value = (bookings, booking_series, True)

        session = self.client.session
        session["booking_data"] = {"rrule": "RRULE:FREQ=WEEKLY;COUNT=5"}
        session.save()

        response = self.client.get(reverse("bookings:preview-booking-series"))
        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/preview-booking-series.html")
        assert "bookings" in response.context
        assert "booking_series" in response.context

    @patch("re_sharing.bookings.views.save_booking_series")
    @patch("re_sharing.bookings.views.create_booking_series_and_bookings")
    def test_post_saves_booking_series(self, mock_create_series, mock_save_series):
        booking_series = BookingSeriesFactory(
            organization=self.organization, resource=self.resource
        )
        bookings = []
        mock_create_series.return_value = (bookings, booking_series, True)
        mock_save_series.return_value = (bookings, booking_series)

        session = self.client.session
        session["booking_data"] = {"rrule": "RRULE:FREQ=WEEKLY;COUNT=5"}
        session.save()

        response = self.client.post(reverse("bookings:preview-booking-series"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse(
            "bookings:show-booking-series", args=[booking_series.slug]
        )
        assert "booking_data" not in self.client.session


class TestListBookingsWebview(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

    @patch("re_sharing.bookings.services.get_external_events")
    @patch("re_sharing.bookings.views.bookings_webview")
    def test_list_bookings_webview(self, mock_bookings_webview, mock_external_events):
        mock_bookings_webview.return_value = ([], "all")
        mock_external_events.return_value = []

        response = self.client.get(reverse("bookings:list-bookings-webview"))

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/list-bookings-webview.html")
        mock_bookings_webview.assert_called_once_with("all")

    @patch("re_sharing.bookings.services.get_external_events")
    @patch("re_sharing.bookings.views.bookings_webview")
    def test_list_bookings_webview_with_filters(
        self, mock_bookings_webview, mock_external_events
    ):
        mock_bookings_webview.return_value = ([], "public")
        mock_external_events.return_value = []

        response = self.client.get(
            reverse("bookings:list-bookings-webview"),
            {"location": "public"},
        )

        assert response.status_code == HTTPStatus.OK
        mock_bookings_webview.assert_called_once_with("public")

    @patch("re_sharing.bookings.services.get_external_events")
    @patch("re_sharing.bookings.views.bookings_webview")
    def test_list_bookings_webview_with_events(
        self, mock_bookings_webview, mock_external_events
    ):
        """Test that external events are included in context."""
        mock_bookings_webview.return_value = ([], "all")
        mock_external_events.return_value = [
            {"title": "Test Event", "start": timezone.now(), "end": None}
        ]

        response = self.client.get(reverse("bookings:list-bookings-webview"))

        assert response.status_code == HTTPStatus.OK
        assert "external_events" in response.context
        assert len(response.context["external_events"]) == 1


class TestManagerListBookingsViewHTMX(TestCase):
    def setUp(self):
        self.manager = ManagerFactory()
        self.client.force_login(self.manager.user)

    @patch("re_sharing.bookings.views.manager_filter_bookings_list")
    def test_htmx_request_returns_partial(self, mock_filter):
        mock_filter.return_value = ([], [], [])

        response = self.client.get(
            reverse("bookings:manager-list-bookings"), headers={"hx-request": "true"}
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "manager-list-bookings")


class TestManagerListBookingSeriesView(TestCase):
    def setUp(self):
        self.manager = ManagerFactory()
        self.client.force_login(self.manager.user)

    @patch("re_sharing.bookings.views.manager_filter_booking_series_list")
    def test_manager_list_booking_series(self, mock_filter):
        mock_filter.return_value = []

        response = self.client.get(reverse("bookings:manager-list-booking_series"))

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/manager_list_booking_series.html")
        mock_filter.assert_called_once()

    @patch("re_sharing.bookings.views.manager_filter_booking_series_list")
    def test_manager_list_booking_series_htmx(self, mock_filter):
        mock_filter.return_value = []

        response = self.client.get(
            reverse("bookings:manager-list-booking_series"),
            headers={"hx-request": "true"},
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "manager-list-booking-series")


class TestManagerCancelBookingSeriesView(TestCase):
    def setUp(self):
        self.manager = ManagerFactory()
        self.booking_series = BookingSeriesFactory()
        self.client.force_login(self.manager.user)

    @patch("re_sharing.bookings.views.manager_cancel_booking_series")
    def test_manager_cancel_booking_series(self, mock_cancel):
        mock_cancel.return_value = self.booking_series

        response = self.client.patch(
            reverse(
                "bookings:manager-cancel-booking-series",
                kwargs={"booking_series_uuid": self.booking_series.uuid},
            )
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "manager-booking-series-item")
        mock_cancel.assert_called_once()


class TestManagerConfirmBookingSeriesView(TestCase):
    def setUp(self):
        self.manager = ManagerFactory()
        self.booking_series = BookingSeriesFactory()
        self.client.force_login(self.manager.user)

    @patch("re_sharing.bookings.views.manager_confirm_booking_series")
    def test_manager_confirm_booking_series(self, mock_confirm):
        mock_confirm.return_value = self.booking_series

        response = self.client.patch(
            reverse(
                "bookings:manager-confirm-booking-series",
                kwargs={"booking_series_uuid": self.booking_series.uuid},
            )
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "manager-booking-series-item")
        mock_confirm.assert_called_once()


class TestManagerFilterInvoiceBookingsListView(TestCase):
    def setUp(self):
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(self.staff_user)

    @patch("re_sharing.bookings.views.manager_filter_invoice_bookings_list")
    def test_manager_filter_invoice_bookings_list(self, mock_filter):
        mock_filter.return_value = ([], [])

        response = self.client.get(reverse("bookings:manager-list-invoices"))

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "bookings/manager_list_invoices.html")
        mock_filter.assert_called_once()

    @patch("re_sharing.bookings.views.manager_filter_invoice_bookings_list")
    def test_manager_filter_invoice_bookings_list_htmx(self, mock_filter):
        mock_filter.return_value = ([], [])

        response = self.client.get(
            reverse("bookings:manager-list-invoices"), headers={"hx-request": "true"}
        )

        assert response.status_code == HTTPStatus.OK
        self.assertTemplateUsed(response, "manager-list-invoices")

    @patch("re_sharing.bookings.views.manager_filter_invoice_bookings_list")
    def test_manager_filter_invoice_bookings_with_filters(self, mock_filter):
        mock_filter.return_value = ([], [])

        response = self.client.get(
            reverse("bookings:manager-list-invoices"),
            {
                "invoice_filter": "paid",
                "organization_search": "test org",
                "invoice_number": "INV-001",
                "resource": "456",
            },
        )

        assert response.status_code == HTTPStatus.OK
        mock_filter.assert_called_once_with("test org", "paid", "INV-001", "456")

    def test_non_staff_user_forbidden(self):
        regular_user = UserFactory(is_staff=False)
        self.client.force_login(regular_user)

        response = self.client.get(reverse("bookings:manager-list-invoices"))
        assert response.status_code == HTTPStatus.FOUND  # Redirects to login
