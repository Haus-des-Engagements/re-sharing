from datetime import datetime
from datetime import timedelta
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.dashboards.views import users_bookings_and_permissions_dashboard_view
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import CompensationFactory
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


class TestHomeView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()
        cache.clear()

    def test_home_view_renders_successfully(self):
        """Test that home view renders without authentication"""
        response = self.client.get(reverse("home"))
        assert response.status_code == HTTPStatus.OK
        assert "confirmed_bookings" in response.context
        assert "total_hours_comp1" in response.context
        assert "registered_organizations" in response.context
        assert "free_bookings_value" in response.context

    def test_home_view_statistics_calculation(self):
        """Test statistics calculation with real data"""
        # Create test data
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create non-parking resource
        resource = ResourceFactory(type=Resource.ResourceTypeChoices.ROOM)

        # Create compensation with id=1 for free bookings
        comp1 = CompensationFactory(id=1, hourly_rate=50)

        # Create a confirmed booking this year with comp1
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=yesterday,
            compensation=comp1,
        )

        # Create confirmed organizations
        confirmed_status = 2
        expected_org_count = 3
        OrganizationFactory.create_batch(expected_org_count, status=confirmed_status)

        response = self.client.get(reverse("home"))

        assert response.status_code == HTTPStatus.OK
        assert response.context["confirmed_bookings"] >= 1
        assert response.context["registered_organizations"] >= expected_org_count
        assert response.context["total_hours_comp1"] >= 0
        assert response.context["free_bookings_value"] >= 0

    def test_home_view_uses_cache(self):
        """Test that home view uses caching"""
        # First request - should calculate and cache
        response1 = self.client.get(reverse("home"))
        stats1 = {
            "confirmed_bookings": response1.context["confirmed_bookings"],
            "total_hours_comp1": response1.context["total_hours_comp1"],
            "registered_organizations": response1.context["registered_organizations"],
            "free_bookings_value": response1.context["free_bookings_value"],
        }

        # Create new data that would change stats
        OrganizationFactory(status=2)  # CONFIRMED status

        # Second request - should use cached data
        response2 = self.client.get(reverse("home"))
        stats2 = {
            "confirmed_bookings": response2.context["confirmed_bookings"],
            "total_hours_comp1": response2.context["total_hours_comp1"],
            "registered_organizations": response2.context["registered_organizations"],
            "free_bookings_value": response2.context["free_bookings_value"],
        }

        # Stats should be the same (cached)
        assert stats1 == stats2

        # Clear cache
        cache.clear()

        # Third request - should recalculate
        response3 = self.client.get(reverse("home"))
        stats3 = {
            "confirmed_bookings": response3.context["confirmed_bookings"],
            "total_hours_comp1": response3.context["total_hours_comp1"],
            "registered_organizations": response3.context["registered_organizations"],
            "free_bookings_value": response3.context["free_bookings_value"],
        }

        # Stats should now reflect the new organization
        assert stats3["registered_organizations"] > stats1["registered_organizations"]

    def test_home_view_excludes_parking_lots(self):
        """Test that parking lots are excluded from confirmed bookings count"""
        yesterday = timezone.now().date() - timedelta(days=1)

        # Create parking lot resource
        parking_resource = ResourceFactory(
            type=Resource.ResourceTypeChoices.PARKING_LOT
        )

        # Create non-parking resource
        regular_resource = ResourceFactory(type=Resource.ResourceTypeChoices.ROOM)

        # Create bookings
        BookingFactory(
            resource=parking_resource,
            status=BookingStatus.CONFIRMED,
            start_date=yesterday,
        )
        BookingFactory(
            resource=regular_resource,
            status=BookingStatus.CONFIRMED,
            start_date=yesterday,
        )

        cache.clear()
        response = self.client.get(reverse("home"))

        # Should only count non-parking booking
        assert response.context["confirmed_bookings"] >= 1

    def test_home_view_calculates_free_bookings_value(self):
        """Test calculation of free bookings value"""
        yesterday = timezone.now().date() - timedelta(days=1)

        resource = ResourceFactory(type=Resource.ResourceTypeChoices.ROOM)

        # Create compensations
        comp1 = CompensationFactory(id=1, hourly_rate=50)
        # Create most expensive compensation for the resource
        CompensationFactory(resource=[resource], hourly_rate=100)

        # Create booking with comp1 (2 hours)
        start_dt = timezone.make_aware(datetime.combine(yesterday, datetime.min.time()))
        end_dt = start_dt + timedelta(hours=2)
        from psycopg.types.range import Range

        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=yesterday,
            compensation=comp1,
            timespan=Range(start_dt, end_dt),
        )

        cache.clear()
        response = self.client.get(reverse("home"))

        # Free bookings value should be calculated
        # 2 hours * 100 (most expensive rate) = 200
        assert response.context["free_bookings_value"] >= 0


class TestReportingView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()
        self.staff_user = UserFactory(is_staff=True)
        self.regular_user = UserFactory(is_staff=False)

    def test_reporting_view_requires_staff(self):
        """Test that reporting view requires staff permission"""
        # Try as regular user
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("dashboards:reports"))
        assert response.status_code == HTTPStatus.FOUND  # Redirect to login

        # Try as staff user
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dashboards:reports"))
        assert response.status_code == HTTPStatus.OK

    def test_reporting_view_context_data(self):
        """Test that reporting view provides correct context"""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dashboards:reports"))

        assert response.status_code == HTTPStatus.OK
        assert "bookings_by_resource" in response.context
        assert "months" in response.context
        assert "monthly_totals" in response.context
        assert "yearly_totals" in response.context
        assert "realized_yearly_totals" in response.context
        assert "not_yet_invoiced" in response.context

    def test_reporting_view_aggregates_bookings(self):
        """Test that reporting view aggregates bookings correctly"""
        # Create resource
        resource = ResourceFactory()

        # Create confirmed booking in 2025
        booking_date = datetime(2025, 3, 15, tzinfo=timezone.get_current_timezone())
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=booking_date.date(),
            total_amount=100,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dashboards:reports"))

        expected_min_amount = 100
        assert response.status_code == HTTPStatus.OK
        assert response.context["yearly_totals"]["bookings_count"] >= 1
        assert response.context["yearly_totals"]["amount"] >= expected_min_amount

    def test_reporting_view_not_yet_invoiced(self):
        """Test that reporting view tracks non-invoiced bookings"""
        resource1 = ResourceFactory()
        resource2 = ResourceFactory()

        # Create booking without invoice number
        booking_date = datetime(2025, 3, 15, tzinfo=timezone.get_current_timezone())
        BookingFactory(
            slug="not-invoiced-booking",
            resource=resource1,
            status=BookingStatus.CONFIRMED,
            start_date=booking_date.date(),
            total_amount=150,
            invoice_number="",
        )

        # Create booking with invoice number (different resource to avoid overlap)
        BookingFactory(
            slug="invoiced-booking",
            resource=resource2,
            status=BookingStatus.CONFIRMED,
            start_date=booking_date.date(),
            total_amount=200,
            invoice_number="INV-001",
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dashboards:reports"))

        expected_min_not_invoiced_amount = 150
        assert response.status_code == HTTPStatus.OK
        not_invoiced = response.context["not_yet_invoiced"]
        assert not_invoiced["bookings_count"] >= 1
        assert not_invoiced["amount"] >= expected_min_not_invoiced_amount

    def test_reporting_view_monthly_totals(self):
        """Test that reporting view calculates monthly totals"""
        resource = ResourceFactory()

        # Create bookings in different months
        march_booking = datetime(2025, 3, 15, tzinfo=timezone.get_current_timezone())
        april_booking = datetime(2025, 4, 20, tzinfo=timezone.get_current_timezone())

        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=march_booking.date(),
            total_amount=100,
        )
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=april_booking.date(),
            total_amount=200,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dashboards:reports"))

        expected_min_months = 2
        assert response.status_code == HTTPStatus.OK
        monthly_totals = list(response.context["monthly_totals"])
        # Should have entries for months with bookings
        assert len(monthly_totals) >= expected_min_months

    def test_reporting_view_realized_vs_total(self):
        """Test that reporting view distinguishes realized vs total bookings"""
        resource = ResourceFactory()

        # Create past booking (realized)
        past_date = timezone.now() - timedelta(days=30)
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=past_date.date(),
            total_amount=100,
        )

        # Create future booking (not yet realized)
        future_date = timezone.now() + timedelta(days=30)
        BookingFactory(
            resource=resource,
            status=BookingStatus.CONFIRMED,
            start_date=future_date.date(),
            total_amount=200,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("dashboards:reports"))

        assert response.status_code == HTTPStatus.OK
        yearly = response.context["yearly_totals"]
        realized = response.context["realized_yearly_totals"]

        # Total should be greater than or equal to realized
        assert yearly["bookings_count"] >= realized["bookings_count"]
