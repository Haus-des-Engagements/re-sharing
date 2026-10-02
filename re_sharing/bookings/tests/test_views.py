import datetime
from http import HTTPStatus
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import make_aware

from re_sharing.bookings.forms import BookingForm
from re_sharing.bookings.models import Booking
from re_sharing.bookings.services import FreeBookingsExhaustedError
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingMessageFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.bookings.views import list_bookings_view
from re_sharing.bookings.views import manager_list_bookings_view
from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.tests.factories import AccessFactory
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

    def test_free_booking_marker(self):
        BookingPermissionFactory(
            organization=self.organization,
            user=self.user,
            status=BookingPermission.Status.CONFIRMED,
        )
        client = Client()
        client.force_login(self.user)

        response = client.get(self.show_booking_url)
        self.assertNotContains(response, "Free booking")

        self.booking.uses_free_booking = True
        self.booking.save()
        response = client.get(self.show_booking_url)
        self.assertContains(response, "Free booking")

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

    @patch("re_sharing.bookings.views.generate_booking")
    def test_get_with_exhausted_free_bookings_redirects_to_form(
        self, mock_generate_booking
    ):
        mock_generate_booking.side_effect = FreeBookingsExhaustedError(2027)
        session = self.client.session
        session["booking_data"] = {
            "start_date": "2027-03-01",
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "resource": self.resource.slug,
            "organization": self.organization.slug,
            "title": "Meeting",
        }
        session.save()

        response = self.client.get(reverse("bookings:preview-booking"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url.startswith(reverse("bookings:create-booking") + "?")
        assert "startdate=2027-03-01" in response.url
        assert "starttime=10%3A00" in response.url
        assert f"resource={self.resource.slug}" in response.url
        assert "booking_data" in self.client.session
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        assert any("2027" in message for message in messages)

    @patch("re_sharing.bookings.views.save_booking")
    @patch("re_sharing.bookings.views.generate_booking")
    def test_post_with_exhausted_free_bookings_creates_no_booking(
        self, mock_generate_booking, mock_save_booking
    ):
        mock_generate_booking.return_value = BookingFactory.build(
            organization=self.organization, resource=self.resource
        )
        mock_save_booking.side_effect = FreeBookingsExhaustedError(2027)
        session = self.client.session
        session["booking_data"] = {"start_date": "2027-03-01"}
        session.save()
        bookings_before = Booking.objects.count()

        response = self.client.post(reverse("bookings:preview-booking"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url.startswith(reverse("bookings:create-booking"))
        assert Booking.objects.count() == bookings_before
        assert "booking_data" in self.client.session

    @patch("re_sharing.bookings.views.generate_booking")
    def test_exhausted_free_bookings_on_edit_redirects_to_update_form(
        self, mock_generate_booking
    ):
        booking = BookingFactory(organization=self.organization, resource=self.resource)
        mock_generate_booking.side_effect = FreeBookingsExhaustedError(2028)
        session = self.client.session
        session["booking_data"] = {"start_date": "2028-03-01", "booking_id": booking.id}
        session.save()

        response = self.client.get(reverse("bookings:preview-booking"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse(
            "bookings:update-booking", kwargs={"booking_slug": booking.slug}
        )

    @patch("re_sharing.bookings.views.generate_booking")
    def test_preview_states_the_free_booking_and_the_remaining_count(
        self, mock_generate_booking
    ):
        self.organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=5,
                free_bookings_valid_from=datetime.date(2027, 1, 1),
            )
        )
        for i in range(2):
            BookingFactory(
                title=f"used-{i}",
                organization=self.organization,
                start_date=datetime.date(2027, 2, 1 + i),
                uses_free_booking=True,
            )
        mock_generate_booking.return_value = BookingFactory.build(
            organization=self.organization,
            resource=self.resource,
            start_date=datetime.date(2027, 3, 1),
            uses_free_booking=True,
        )
        session = self.client.session
        session["booking_data"] = {"start_date": "2027-03-01"}
        session.save()

        response = self.client.get(reverse("bookings:preview-booking"))

        self.assertContains(response, "Free booking")
        self.assertContains(response, "Afterwards 2 free bookings remain for 2027.")

    @patch("re_sharing.bookings.views.generate_booking")
    def test_preview_of_a_paid_booking_has_no_free_booking_note(
        self, mock_generate_booking
    ):
        mock_generate_booking.return_value = BookingFactory.build(
            organization=self.organization,
            resource=self.resource,
            start_date=datetime.date(2027, 3, 1),
            uses_free_booking=False,
        )
        session = self.client.session
        session["booking_data"] = {"start_date": "2027-03-01"}
        session.save()

        response = self.client.get(reverse("bookings:preview-booking"))

        self.assertNotContains(response, "Free booking")


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
        mock_create_series.return_value = (bookings, booking_series, True, {})

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
        mock_create_series.return_value = (bookings, booking_series, True, {})
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


class TestPreviewBookingSeriesPricingView(TestCase):
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
        session = self.client.session
        session["booking_data"] = {"rrule": "RRULE:FREQ=WEEKLY;COUNT=5"}
        session.save()

    @patch("re_sharing.bookings.views.create_booking_series_and_bookings")
    def test_preview_shows_the_pricing_breakdown(self, mock_create_series):
        booking_series = BookingSeriesFactory.build(
            organization=self.organization, resource=self.resource
        )
        mock_create_series.return_value = (
            [],
            booking_series,
            True,
            {
                "free": 5,
                "paid": 47,
                "unavailable": 0,
                "dropped": 0,
                "rate": 15,
                "total": 1410,
            },
        )

        response = self.client.get(reverse("bookings:preview-booking-series"))

        self.assertContains(response, "5 free bookings")
        self.assertContains(response, "47 bookings charged at 15 €/hour")
        self.assertContains(response, "1410.00 €")
        self.assertNotContains(response, "cannot be created")

    @patch("re_sharing.bookings.views.create_booking_series_and_bookings")
    def test_preview_mentions_dropped_occurrences(self, mock_create_series):
        booking_series = BookingSeriesFactory.build(
            organization=self.organization, resource=self.resource
        )
        mock_create_series.return_value = (
            [],
            booking_series,
            True,
            {
                "free": 2,
                "paid": 0,
                "unavailable": 0,
                "dropped": 3,
                "rate": None,
                "total": 0,
            },
        )

        response = self.client.get(reverse("bookings:preview-booking-series"))

        self.assertContains(response, "3 bookings cannot be created")


class TestShowBookingSeriesPricingView(TestCase):
    def test_occurrences_show_amount_and_free_booking_marker(self):
        user = UserFactory()
        organization = OrganizationFactory()
        BookingPermissionFactory(
            user=user,
            organization=organization,
            status=BookingPermission.Status.CONFIRMED,
        )
        booking_series = BookingSeriesFactory(organization=organization)
        BookingFactory(
            title="free-occurrence",
            booking_series=booking_series,
            organization=organization,
            uses_free_booking=True,
            start_date=datetime.date(2027, 3, 1),
        )
        BookingFactory(
            title="paid-occurrence",
            booking_series=booking_series,
            organization=organization,
            total_amount=30,
            start_date=datetime.date(2027, 3, 8),
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse("bookings:show-booking-series", args=[booking_series.slug])
        )

        self.assertContains(response, "Free booking")
        self.assertContains(response, "(30.00 €)")


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

    def test_row_shows_free_booking_marker(self):
        group = OrganizationGroupFactory()
        self.manager.organization_groups.add(group)
        organization = OrganizationFactory()
        organization.organization_groups.add(group)
        resource = ResourceFactory()
        self.manager.resources.add(resource)
        start = timezone.now() + datetime.timedelta(days=3)
        BookingFactory(
            title="free-one",
            organization=organization,
            resource=resource,
            booking_series=None,
            status=BookingStatus.PENDING,
            timespan=(start, start + datetime.timedelta(hours=2)),
            uses_free_booking=True,
        )

        response = self.client.get(
            reverse("bookings:manager-list-bookings"), headers={"hx-request": "true"}
        )

        self.assertContains(response, "free-one")
        self.assertContains(response, "Free booking")


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
        mock_filter.assert_called_once_with(
            "test org", "paid", "INV-001", "456", "all", "past"
        )

    def test_non_staff_user_forbidden(self):
        regular_user = UserFactory(is_staff=False)
        self.client.force_login(regular_user)

        response = self.client.get(reverse("bookings:manager-list-invoices"))
        assert response.status_code == HTTPStatus.FOUND  # Redirects to login


class TestCreateItemBookingViewPublicAccess(TestCase):
    """create_item_booking_view is public; shows a notice when login/org is missing."""

    URL = "bookings:create-item-booking"
    NOTICE_TEXT = b"item-booking-login-notice"

    def setUp(self):
        from re_sharing.resources.models import Resource
        from re_sharing.resources.tests.factories import ResourceFactory

        self.client = Client()
        ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=3,
        )

    def test_anonymous_user_can_access_page(self):
        """Non-logged-in users can view the item listing."""
        response = self.client.get(reverse(self.URL))
        assert response.status_code == HTTPStatus.OK

    def test_anonymous_user_sees_items(self):
        """Items are displayed for anonymous users."""
        response = self.client.get(reverse(self.URL))
        assert len(response.context["items"]) > 0

    def test_anonymous_user_sees_notice(self):
        """Anonymous users see the login/org notice."""
        response = self.client.get(reverse(self.URL))
        assert self.NOTICE_TEXT in response.content

    def test_logged_in_user_without_org_sees_notice(self):
        """Users without a confirmed organisation see the notice."""
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(reverse(self.URL))
        assert response.status_code == HTTPStatus.OK
        assert self.NOTICE_TEXT in response.content

    def test_logged_in_user_with_approved_org_sees_no_notice(self):
        """Users with a confirmed booking permission see no notice."""
        user = UserFactory()
        ManagerFactory(user=user)
        org = OrganizationFactory()
        BookingPermissionFactory(
            user=user,
            organization=org,
            status=BookingPermission.Status.CONFIRMED,
        )
        self.client.force_login(user)
        response = self.client.get(reverse(self.URL))
        assert response.status_code == HTTPStatus.OK
        assert self.NOTICE_TEXT not in response.content


class TestPreviewItemBookingEligibility(TestCase):
    """Only organizations in group 4 may proceed to the item booking preview."""

    ELIGIBLE_GROUP_ID = 4
    URL = "bookings:preview-item-booking"

    def setUp(self):
        from re_sharing.organizations.models import OrganizationGroup
        from re_sharing.organizations.tests.factories import OrganizationGroupFactory

        self.client = Client()

        # Ensure the eligible group with the fixed id exists
        self.eligible_group, _ = OrganizationGroup.objects.get_or_create(
            pk=self.ELIGIBLE_GROUP_ID,
            defaults={"name": "Item Booking Eligible", "description": ""},
        )

        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)

        self.regular_user = UserFactory()

        self.eligible_org = OrganizationFactory()
        self.eligible_org.organization_groups.add(self.eligible_group)
        BookingPermissionFactory(
            user=self.regular_user,
            organization=self.eligible_org,
            status=BookingPermission.Status.CONFIRMED,
        )

        self.ineligible_org = OrganizationFactory()
        other_group = OrganizationGroupFactory()
        self.ineligible_org.organization_groups.add(other_group)
        BookingPermissionFactory(
            user=self.regular_user,
            organization=self.ineligible_org,
            status=BookingPermission.Status.CONFIRMED,
        )

    def _htmx_post(self, org_id):
        return self.client.post(
            reverse(self.URL),
            data={
                "organization": org_id,
                "pickup_date": "2026-03-02",
                "return_date": "2026-03-03",
            },
            headers={"hx-request": "true"},
        )

    def test_ineligible_org_gets_restriction_modal(self):
        """Regular users with ineligible org get restriction modal."""
        self.client.force_login(self.regular_user)
        response = self._htmx_post(self.ineligible_org.pk)
        assert response.status_code == HTTPStatus.OK
        assert b"not eligible" in response.content

    def test_eligible_org_does_not_get_restriction(self):
        """Eligible org does not trigger the restriction message."""
        self.client.force_login(self.regular_user)
        response = self._htmx_post(self.eligible_org.pk)
        assert b"not eligible" not in response.content

    def test_manager_bypasses_eligibility_check(self):
        """Managers can book for any org, even ineligible ones."""
        self.client.force_login(self.manager_user)
        response = self._htmx_post(self.ineligible_org.pk)
        assert b"not eligible" not in response.content

    def test_anonymous_user_gets_login_required_modal(self):
        """Non-logged-in users receive a login-required modal."""
        response = self._htmx_post(self.eligible_org.pk)
        assert response.status_code == HTTPStatus.OK
        assert b"log in" in response.content


class TestManagerItemBookingOrganizationSelection(TestCase):
    """Managers can book items for any organization, not just their own."""

    URL = "bookings:create-item-booking"

    def setUp(self):
        from re_sharing.organizations.models import OrganizationGroup
        from re_sharing.resources.models import Resource
        from re_sharing.resources.tests.factories import ResourceFactory

        self.client = Client()
        ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=3,
        )

        eligible_group, _ = OrganizationGroup.objects.get_or_create(
            pk=4,
            defaults={"name": "Item Booking Eligible", "description": ""},
        )

        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)

        # org the manager belongs to
        self.own_org = OrganizationFactory()
        self.own_org.organization_groups.add(eligible_group)
        BookingPermissionFactory(
            user=self.manager_user,
            organization=self.own_org,
            status=BookingPermission.Status.CONFIRMED,
        )

        # org the manager does NOT belong to
        self.other_org = OrganizationFactory()
        self.other_org.organization_groups.add(eligible_group)

        self.regular_user = UserFactory()
        BookingPermissionFactory(
            user=self.regular_user,
            organization=self.own_org,
            status=BookingPermission.Status.CONFIRMED,
        )

    def test_manager_sees_all_organizations_in_dropdown(self):
        """Managers see every organization in the org dropdown, not just their own."""
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        assert response.status_code == HTTPStatus.OK
        org_ids = [org.pk for org in response.context["organizations"]]
        assert self.own_org.pk in org_ids
        assert self.other_org.pk in org_ids

    def test_regular_user_only_sees_own_organizations(self):
        """Regular users only see organizations they belong to."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse(self.URL))
        assert response.status_code == HTTPStatus.OK
        org_ids = [org.pk for org in response.context["organizations"]]
        assert self.own_org.pk in org_ids
        assert self.other_org.pk not in org_ids


class TestPrivateLendableItemVisibility(TestCase):
    """Private lendable items are only shown to managers."""

    URL = "bookings:create-item-booking"

    def setUp(self):
        from re_sharing.resources.models import Resource
        from re_sharing.resources.tests.factories import ResourceFactory

        self.client = Client()
        self.public_item = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=3,
            is_private=False,
        )
        self.private_item = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=2,
            is_private=True,
        )
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)

        self.regular_user = UserFactory()
        org = OrganizationFactory()
        BookingPermissionFactory(
            user=self.regular_user,
            organization=org,
            status=BookingPermission.Status.CONFIRMED,
        )

    def _item_pks(self, response):
        return [item["resource"].pk for item in response.context["items"]]

    def test_private_item_hidden_from_anonymous_user(self):
        response = self.client.get(reverse(self.URL))
        assert self.public_item.pk in self._item_pks(response)
        assert self.private_item.pk not in self._item_pks(response)

    def test_private_item_hidden_from_regular_user(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse(self.URL))
        assert self.public_item.pk in self._item_pks(response)
        assert self.private_item.pk not in self._item_pks(response)

    def test_private_item_visible_to_manager(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        pks = self._item_pks(response)
        assert self.public_item.pk in pks
        assert self.private_item.pk in pks


class TestCreateDraftInvoiceView(TestCase):
    def setUp(self):
        from psycopg.types.range import Range

        from re_sharing.resources.tests.factories import CompensationFactory
        from re_sharing.resources.tests.factories import ResourceFactory

        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(self.staff_user)

        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        # Past booking without invoice number
        import zoneinfo

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2025, 1, 15, 16, 0, tzinfo=tz)
        end = datetime.datetime(2025, 1, 15, 19, 0, tzinfo=tz)
        self.booking = BookingFactory(
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            invoice_number="",
            timespan=Range(start, end),
            start_date=start.date(),
            end_date=end.date(),
            start_time=start.time(),
            end_time=end.time(),
        )

    @patch("re_sharing.bookings.tasks.create_draft_invoice")
    def test_creates_draft_invoice_for_past_booking(self, mock_task):
        response = self.client.post(
            reverse(
                "bookings:create-draft-invoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK
        mock_task.enqueue.assert_called_once_with(self.booking.id)

    @patch("re_sharing.bookings.tasks.create_draft_invoice")
    def test_rejects_booking_with_existing_invoice_number(self, mock_task):
        self.booking.invoice_number = "INV-001"
        self.booking.save()

        response = self.client.post(
            reverse(
                "bookings:create-draft-invoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_task.enqueue.assert_not_called()

    @patch("re_sharing.bookings.tasks.create_draft_invoice")
    def test_rejects_future_booking(self, mock_task):
        import zoneinfo

        from psycopg.types.range import Range

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        future_start = datetime.datetime(2027, 6, 15, 16, 0, tzinfo=tz)
        future_end = datetime.datetime(2027, 6, 15, 19, 0, tzinfo=tz)
        self.booking.timespan = Range(future_start, future_end)
        self.booking.save()

        response = self.client.post(
            reverse(
                "bookings:create-draft-invoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_task.enqueue.assert_not_called()

    def test_non_staff_user_forbidden(self):
        regular_user = UserFactory(is_staff=False)
        self.client.force_login(regular_user)

        response = self.client.post(
            reverse(
                "bookings:create-draft-invoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )
        assert response.status_code == HTTPStatus.FOUND


class TestCreateEinvoiceView(TestCase):
    def setUp(self):
        import zoneinfo

        from psycopg.types.range import Range

        from re_sharing.organizations.tests.factories import OrganizationFactory
        from re_sharing.resources.tests.factories import CompensationFactory
        from re_sharing.resources.tests.factories import ResourceFactory

        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(self.staff_user)

        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2025, 1, 15, 16, 0, tzinfo=tz)
        end = datetime.datetime(2025, 1, 15, 19, 0, tzinfo=tz)
        organization = OrganizationFactory()
        self.booking = BookingFactory(
            organization=organization,
            user=self.staff_user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            timespan=Range(start, end),
            start_date=start.date(),
            end_date=end.date(),
            start_time=start.time(),
            end_time=end.time(),
        )

    @patch("re_sharing.bookings.tasks.create_einvoice")
    def test_creates_einvoice_for_past_booking(self, mock_task):
        response = self.client.post(
            reverse(
                "bookings:create-einvoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK
        mock_task.enqueue.assert_called_once_with(self.booking.id)

    @patch("re_sharing.bookings.tasks.create_einvoice")
    def test_rejects_booking_with_invoice_number(self, mock_task):
        self.booking.invoice_number = "INV-001"
        self.booking.save()

        response = self.client.post(
            reverse(
                "bookings:create-einvoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_task.enqueue.assert_not_called()

    @patch("re_sharing.bookings.tasks.create_einvoice")
    def test_rejects_future_booking(self, mock_task):
        import zoneinfo

        from psycopg.types.range import Range

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        future_start = datetime.datetime(2027, 6, 15, 16, 0, tzinfo=tz)
        future_end = datetime.datetime(2027, 6, 15, 19, 0, tzinfo=tz)
        self.booking.timespan = Range(future_start, future_end)
        self.booking.save()

        response = self.client.post(
            reverse(
                "bookings:create-einvoice",
                kwargs={"booking_slug": self.booking.slug},
            )
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_task.enqueue.assert_not_called()


class TestCreateOrgDraftInvoiceView(TestCase):
    def setUp(self):
        import zoneinfo

        from psycopg.types.range import Range

        from re_sharing.resources.tests.factories import CompensationFactory
        from re_sharing.resources.tests.factories import ResourceFactory

        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(self.staff_user)

        self.organization = OrganizationFactory(
            name="Test Organisation e.V.",
            street_and_housenb="Teststraße 1",
            zip_code="79100",
            city="Freiburg",
            email="test@example.com",
        )
        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start1 = datetime.datetime(2025, 1, 15, 16, 0, tzinfo=tz)
        end1 = datetime.datetime(2025, 1, 15, 19, 0, tzinfo=tz)
        self.booking1 = BookingFactory(
            organization=self.organization,
            user=self.staff_user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            invoice_number="",
            timespan=Range(start1, end1),
            start_date=start1.date(),
            end_date=end1.date(),
            start_time=start1.time(),
            end_time=end1.time(),
        )

        start2 = datetime.datetime(2025, 1, 20, 10, 0, tzinfo=tz)
        end2 = datetime.datetime(2025, 1, 20, 12, 30, tzinfo=tz)
        self.booking2 = BookingFactory(
            organization=self.organization,
            user=self.staff_user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=30,
            invoice_number="",
            timespan=Range(start2, end2),
            start_date=start2.date(),
            end_date=end2.date(),
            start_time=start2.time(),
            end_time=end2.time(),
        )

    @patch("re_sharing.bookings.tasks.create_org_draft_invoice")
    def test_creates_org_draft_invoice(self, mock_task):
        response = self.client.post(
            reverse(
                "bookings:create-org-draft-invoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK
        mock_task.enqueue.assert_called_once_with(self.organization.id)

    @patch("re_sharing.bookings.tasks.create_org_draft_invoice")
    def test_skips_bookings_with_single_invoice_flag(self, mock_task):
        self.booking1.invoice_address = {"single_invoice": True}
        self.booking1.save()

        response = self.client.post(
            reverse(
                "bookings:create-org-draft-invoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK
        mock_task.enqueue.assert_called_once_with(self.organization.id)

    @patch("re_sharing.bookings.tasks.create_org_draft_invoice")
    def test_rejects_when_no_uninvoiced_bookings(self, mock_task):
        self.booking1.invoice_number = "INV-001"
        self.booking1.save()
        self.booking2.invoice_number = "INV-002"
        self.booking2.save()

        response = self.client.post(
            reverse(
                "bookings:create-org-draft-invoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_task.enqueue.assert_not_called()

    def test_non_staff_user_forbidden(self):
        regular_user = UserFactory(is_staff=False)
        self.client.force_login(regular_user)

        response = self.client.post(
            reverse(
                "bookings:create-org-draft-invoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )
        assert response.status_code == HTTPStatus.FOUND


class TestCreateOrgEinvoiceView(TestCase):
    def setUp(self):
        import zoneinfo

        from psycopg.types.range import Range

        from re_sharing.resources.tests.factories import CompensationFactory
        from re_sharing.resources.tests.factories import ResourceFactory

        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(self.staff_user)

        self.organization = OrganizationFactory(
            name="Test Organisation e.V.",
            street_and_housenb="Teststraße 1",
            zip_code="79100",
            city="Freiburg",
            email="test@example.com",
        )
        self.resource = ResourceFactory(name="Veranstaltungsraum")
        self.compensation = CompensationFactory(hourly_rate=12)
        self.compensation.resource.add(self.resource)

        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        start1 = datetime.datetime(2025, 1, 15, 16, 0, tzinfo=tz)
        end1 = datetime.datetime(2025, 1, 15, 19, 0, tzinfo=tz)
        self.booking1 = BookingFactory(
            organization=self.organization,
            user=self.staff_user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=36,
            invoice_number="",
            timespan=Range(start1, end1),
            start_date=start1.date(),
            end_date=end1.date(),
            start_time=start1.time(),
            end_time=end1.time(),
        )

        start2 = datetime.datetime(2025, 1, 20, 10, 0, tzinfo=tz)
        end2 = datetime.datetime(2025, 1, 20, 12, 30, tzinfo=tz)
        self.booking2 = BookingFactory(
            organization=self.organization,
            user=self.staff_user,
            resource=self.resource,
            compensation=self.compensation,
            status=BookingStatus.CONFIRMED,
            total_amount=30,
            invoice_number="",
            timespan=Range(start2, end2),
            start_date=start2.date(),
            end_date=end2.date(),
            start_time=start2.time(),
            end_time=end2.time(),
        )

    @patch("re_sharing.bookings.tasks.create_org_einvoice")
    def test_creates_org_einvoice(self, mock_task):
        response = self.client.post(
            reverse(
                "bookings:create-org-einvoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK
        mock_task.enqueue.assert_called_once_with(self.organization.id)

    @patch("re_sharing.bookings.tasks.create_org_einvoice")
    def test_skips_bookings_with_single_invoice_flag(self, mock_task):
        self.booking1.invoice_address = {"single_invoice": True}
        self.booking1.save()

        response = self.client.post(
            reverse(
                "bookings:create-org-einvoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK
        mock_task.enqueue.assert_called_once_with(self.organization.id)

    @patch("re_sharing.bookings.tasks.create_org_einvoice")
    def test_rejects_when_no_uninvoiced_bookings(self, mock_task):
        self.booking1.invoice_number = "INV-001"
        self.booking1.save()
        self.booking2.invoice_number = "INV-002"
        self.booking2.save()

        response = self.client.post(
            reverse(
                "bookings:create-org-einvoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        mock_task.enqueue.assert_not_called()

    def test_non_staff_user_forbidden(self):
        regular_user = UserFactory(is_staff=False)
        self.client.force_login(regular_user)

        response = self.client.post(
            reverse(
                "bookings:create-org-einvoice",
                kwargs={"organization_slug": self.organization.slug},
            )
        )
        assert response.status_code == HTTPStatus.FOUND


class TestManagerItemBookingsPastFilter(TestCase):
    """Tests for the show-past-bookings filter on the manager item bookings view."""

    URL = "bookings:manager-item-bookings"

    def setUp(self):
        from psycopg.types.range import Range

        from re_sharing.bookings.models import BookingGroup

        self.Range = Range
        self.BookingGroup = BookingGroup
        self.client = Client()
        self.manager_user = ManagerFactory().user
        self.organization = OrganizationFactory()

        now = timezone.now()
        # A group whose booking is fully over (returned yesterday).
        self.past_group = self._make_group(now - datetime.timedelta(days=1))
        # A group whose booking is not yet fully over (returns tomorrow).
        self.active_group = self._make_group(now + datetime.timedelta(days=1))

    def _make_group(self, end_datetime, status=BookingStatus.CONFIRMED):
        group = self.BookingGroup.objects.create(
            organization=self.organization,
            user=self.manager_user,
            status=status,
        )
        start_datetime = end_datetime - datetime.timedelta(hours=2)
        BookingFactory(
            booking_group=group,
            organization=self.organization,
            user=self.manager_user,
            status=status,
            start_date=start_datetime.date(),
            end_date=end_datetime.date(),
            timespan=self.Range(start_datetime, end_datetime),
        )
        return group

    def test_requires_manager(self):
        self.client.force_login(UserFactory(is_staff=False))
        response = self.client.get(reverse(self.URL))
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_hides_past_groups_by_default(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        groups = list(response.context["booking_groups"])
        assert self.active_group in groups
        assert self.past_group not in groups

    def test_shows_past_groups_when_requested(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL), {"show_past_bookings": "on"})
        groups = list(response.context["booking_groups"])
        assert self.active_group in groups
        assert self.past_group in groups

    def test_show_past_bookings_in_context(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        assert response.context["show_past_bookings"] is False
        response = self.client.get(reverse(self.URL), {"show_past_bookings": "on"})
        assert response.context["show_past_bookings"]


class TestManagerListBookingsAccessCodeSearch(TestCase):
    """
    The access code search at /bookings/manage-bookings/ has to find the
    booking a caller is asking about, which is normally confirmed, may already
    have ended, and is not necessarily in the current filter selection.
    """

    def setUp(self):
        self.manager = ManagerFactory()
        self.user = self.manager.user
        self.organization_group = OrganizationGroupFactory()
        self.manager.organization_groups.add(self.organization_group)

        self.organization = OrganizationFactory(name="Managed Org")
        self.organization.organization_groups.add(self.organization_group)

        self.access = AccessFactory(name="code search access", smartlock_id="lock-1")
        self.resource = ResourceFactory(name="Code Search Room", access=self.access)
        self.manager.resources.add(self.resource)

        self.url = reverse("bookings:manager-list-bookings")
        self.client.force_login(self.user)

    def _make_booking(self, days, access_code="345678", status=BookingStatus.CONFIRMED):
        start = timezone.now() + timezone.timedelta(days=days)
        booking = BookingFactory(
            user=self.user,
            organization=self.organization,
            resource=self.resource,
            booking_series=None,
            status=status,
            timespan=(start, start + timezone.timedelta(hours=2)),
            access_code=access_code,
        )
        booking.refresh_from_db()
        return booking

    # --- relaxed defaults --------------------------------------------------

    def test_finds_confirmed_booking_under_default_status_filter(self):
        """The list defaults to pending; a caller's booking is confirmed."""
        booking = self._make_booking(days=1)

        response = self.client.get(self.url, {"access_code": "345678"})

        assert list(response.context["bookings"]) == [booking]

    def test_finds_already_ended_booking_under_default_past_filter(self):
        booking = self._make_booking(days=-2)

        response = self.client.get(self.url, {"access_code": "345678"})

        assert list(response.context["bookings"]) == [booking]

    def test_relaxed_filters_are_reported_as_relaxed(self):
        self._make_booking(days=1)

        response = self.client.get(self.url, {"access_code": "345678"})

        assert response.context["code_search_active"] is True
        assert response.context["selected_status"] == "all"
        assert response.context["show_past_bookings"] is True
        assert response.context["show_recurring_bookings"] is True

    def test_submitted_status_does_not_narrow_a_code_search(self):
        """The form always submits a status, so it cannot narrow the search."""
        booking = self._make_booking(days=1)

        response = self.client.get(self.url, {"access_code": "345678", "status": "1"})

        assert list(response.context["bookings"]) == [booking]

    def test_status_filter_still_applies_without_a_code_search(self):
        self._make_booking(days=1)

        response = self.client.get(self.url, {"status": "1"})

        assert list(response.context["bookings"]) == []

    # --- date window -------------------------------------------------------

    def test_default_window_is_applied_and_reported(self):
        self._make_booking(days=1)

        response = self.client.get(self.url, {"access_code": "345678"})

        window = response.context["access_code_window"]
        assert window is not None
        today = timezone.now().date()
        assert window[0] == today - timezone.timedelta(days=7)
        assert window[1] == today + timezone.timedelta(days=90)

    def test_default_window_excludes_a_far_future_booking(self):
        self._make_booking(days=200)

        response = self.client.get(self.url, {"access_code": "345678"})

        assert list(response.context["bookings"]) == []

    def test_show_all_dates_removes_the_window(self):
        booking = self._make_booking(days=200)

        response = self.client.get(
            self.url, {"access_code": "345678", "all_dates": "on"}
        )

        assert response.context["access_code_window"] is None
        assert list(response.context["bookings"]) == [booking]

    def test_explicit_date_range_wins_over_the_default_window(self):
        self._make_booking(days=30)

        response = self.client.get(
            self.url,
            {
                "access_code": "345678",
                "until_date": (timezone.now() + timezone.timedelta(days=5))
                .date()
                .isoformat(),
            },
        )

        assert response.context["access_code_window"] is None
        assert list(response.context["bookings"]) == []

    def test_no_window_without_a_code_search(self):
        response = self.client.get(self.url)

        assert response.context["access_code_window"] is None
        assert response.context["code_search_active"] is False

    # --- rendering ---------------------------------------------------------

    def test_code_column_is_rendered_during_a_code_search(self):
        self._make_booking(days=1)

        response = self.client.get(self.url, {"access_code": "345678"})

        self.assertContains(response, "345678")

    def test_code_column_is_absent_without_a_code_search(self):
        self._make_booking(days=1)

        response = self.client.get(self.url, {"status": "all"})

        self.assertNotContains(response, "<code>")

    def test_htmx_request_renders_the_partial(self):
        booking = self._make_booking(days=1)

        response = self.client.get(
            self.url, {"access_code": "345678"}, headers={"hx-request": "true"}
        )

        assert response.status_code == HTTPStatus.OK
        assert list(response.context["bookings"]) == [booking]
        self.assertTemplateUsed(response, "manager-list-bookings")

    def test_htmx_partial_does_not_leak_template_syntax(self):
        """Django's {# #} only comments a single line; a wrapped one renders."""
        self._make_booking(days=1)

        response = self.client.get(
            self.url, {"access_code": "345678"}, headers={"hx-request": "true"}
        )

        body = response.content.decode()
        assert "{#" not in body
        assert "#}" not in body
        assert "{% comment" not in body

    def test_too_short_code_is_not_a_search(self):
        self._make_booking(days=1, status=BookingStatus.PENDING)

        response = self.client.get(self.url, {"access_code": "34"})

        assert response.context["code_search_active"] is False
        assert response.context["access_code_window"] is None

    # --- permissions -------------------------------------------------------

    def test_non_manager_is_denied(self):
        self.client.force_login(UserFactory(is_staff=False))

        response = self.client.get(self.url, {"access_code": "345678"})

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(self.url, {"access_code": "345678"})

        assert response.status_code == HTTPStatus.FOUND
        assert "login" in response.url
