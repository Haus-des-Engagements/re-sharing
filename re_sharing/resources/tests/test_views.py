from datetime import datetime
from datetime import time
from datetime import timedelta
from http import HTTPStatus

import pytest
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.models import AccessCode
from re_sharing.resources.tests.factories import AccessCodeFactory
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.resources.tests.factories import ResourceRestrictionFactory
from re_sharing.resources.views import get_compensations
from re_sharing.resources.views import list_resources_view
from re_sharing.resources.views import planner_view
from re_sharing.resources.views import show_resource_view
from re_sharing.users.tests.factories import UserFactory


class ShowResourceViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.resource = ResourceFactory()

    def test_show_resource_view(self):
        request = self.factory.get(
            reverse(
                "resources:show-resource", kwargs={"resource_slug": self.resource.slug}
            ),
        )
        response = show_resource_view(request, resource_slug=self.resource.slug)
        assert response.status_code == HTTPStatus.OK
        assert self.resource.name in response.content.decode()

    @pytest.mark.django_db()
    def test_show_resource_view_hx_request(self):
        # Send GET request to the view with 'HX-Request' in headers
        request = self.factory.get(
            reverse(
                "resources:show-resource", kwargs={"resource_slug": self.resource.slug}
            ),
            HTTP_HX_REQUEST="true",
        )
        response = show_resource_view(request, resource_slug=self.resource.slug)

        # Check status code of the response
        assert response.status_code == HTTPStatus.OK


class ResourceListViewTest(TestCase):
    def setUp(self):
        self.resource1 = ResourceFactory(slug="green")
        self.resource2 = ResourceFactory(slug="blue")
        self.factory = RequestFactory()
        self.user = UserFactory()

    def test_resource_list_view(self):
        request = self.factory.get(reverse("resources:list-resources"))
        request.user = self.user
        response = list_resources_view(request)
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.django_db()
    def test_list_resources_view_hx_request(self):
        # Send GET request to the view with 'HX-Request' in headers
        request = self.factory.get(
            reverse("resources:list-resources"), HTTP_HX_REQUEST="true"
        )
        request.user = self.user
        response = list_resources_view(request)

        # Check status code of the response
        assert response.status_code == HTTPStatus.OK


class PlannerViewTest(TestCase):
    def setUp(self):
        self.resource1 = ResourceFactory(slug="green")
        self.resource2 = ResourceFactory(slug="blue")
        self.factory = RequestFactory()
        self.user = UserFactory()

    def test_planner_view(self):
        request = self.factory.get(reverse("resources:planner"))
        request.user = self.user
        response = planner_view(request)
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.django_db()
    def test_planner_view_hx_request(self):
        # Send GET request to the view with 'HX-Request' in headers
        request = self.factory.get(reverse("resources:planner"), HTTP_HX_REQUEST="true")
        request.user = self.user
        response = planner_view(request)

        # Check status code of the response
        assert response.status_code == HTTPStatus.OK


class ResourceRestrictionModelTest(TestCase):
    """
    Additional tests for the ResourceRestriction model functionality.
    These tests focus on the integration with the planner and get_compensations views.
    """

    def setUp(self):
        self.resource = ResourceFactory(slug="restricted-resource")
        self.organization = OrganizationFactory()

        # Create a restriction for weekdays (Monday-Friday) from 00:00 to 18:00
        self.restriction_message = "This resource is restricted during these hours"
        self.restriction = ResourceRestrictionFactory(
            resources=[self.resource],
            start_time=time(0, 0),
            end_time=time(18, 0),
            days_of_week="0,1,2,3,4",  # Monday to Friday
            message=self.restriction_message,
        )

    def test_restriction_applies_to_datetime_weekday(self):
        """
        Test that the restriction applies to a datetime on a weekday within the time
        range.
        """
        # Monday at 12:00
        monday_noon = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=28, hour=12, minute=0, second=0, microsecond=0
        )
        assert self.restriction.applies_to_datetime(monday_noon)

    def test_restriction_does_not_apply_to_datetime_weekend(self):
        """
        Test that the restriction does not apply to a datetime on a weekend.
        """
        # Saturday at 12:00
        saturday_noon = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=26, hour=12, minute=0, second=0, microsecond=0
        )
        assert not self.restriction.applies_to_datetime(saturday_noon)

    def test_restriction_does_not_apply_to_datetime_outside_hours(self):
        """
        Test that the restriction does not apply to a datetime outside the time range.
        """
        # Monday at 19:00 (after 18:00)
        monday_evening = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=28, hour=19, minute=0, second=0, microsecond=0
        )
        assert not self.restriction.applies_to_datetime(monday_evening)

    def test_restriction_applies_to_organization(self):
        """
        Test that the restriction applies to an organization not in an exempt group.
        """
        assert self.restriction.applies_to_organization(self.organization)

    def test_restriction_does_not_apply_to_exempt_organization(self):
        """
        Test that the restriction does not apply to an organization in an exempt group.
        """
        # Create an organization group and add it to the organization
        org_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(org_group)

        # Update the restriction to exempt the organization group
        self.restriction.exempt_organization_groups.add(org_group)

        assert not self.restriction.applies_to_organization(self.organization)


class GetCompensationsViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.resource = ResourceFactory(name="Test Resource")
        self.organization = OrganizationFactory()
        self.compensation_name = "For Free"
        self.compensation = CompensationFactory(name=self.compensation_name)
        self.compensation.resource.add(self.resource)
        # Create organization groups without specifying IDs to avoid conflicts
        OrganizationGroupFactory()
        OrganizationGroupFactory()

    def test_get_compensations_empty_resource(self):
        request = self.factory.post(
            reverse("resources:get-compensations", kwargs={"selected_compensation": 1})
        )
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        assert str(_("Please select a resource first.")) in response.content.decode()

    def test_get_compensations_with_resource(self):
        request = self.factory.post(
            reverse("resources:get-compensations", kwargs={"selected_compensation": 1}),
            {
                "resource": self.resource.id,
                "organization": self.organization.id,
                "starttime": "19:00",
                "startdate": "2025-04-29",
            },
        )
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        assert self.compensation_name in response.content.decode()

    def test_get_compensations_with_restriction(self):
        # Create a restriction for weekdays (Monday-Friday) from 00:00 to 18:00
        restriction_message = "This resource is restricted during these hours"
        ResourceRestrictionFactory(
            resources=[self.resource],
            start_time=time(0, 0),
            end_time=time(18, 0),
            days_of_week="0,1,2,3,4",  # Monday to Friday
            message=restriction_message,
        )

        # Test with a time that falls within the restriction (Monday at 12:00)
        request = self.factory.post(
            reverse("resources:get-compensations", kwargs={"selected_compensation": 1}),
            {
                "resource": self.resource.id,
                "organization": self.organization.id,
                "starttime": "12:00",
                "startdate": "2025-04-28",  # A Monday
            },
        )
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        assert restriction_message in response.content.decode()

    def test_get_compensations_with_exempt_organization(self):
        # Create an organization group and add it to the organization
        org_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(org_group)

        # Create a restriction with the organization group as exempt
        ResourceRestrictionFactory(
            resources=[self.resource],
            exempt_organization_groups=[org_group],
            start_time=time(0, 0),
            end_time=time(18, 0),
            days_of_week="0,1,2,3,4",  # Monday to Friday
        )

        # Test with a time that falls within the restriction but with an exempt
        # organization
        # The organization should be exempt from the restriction
        request = self.factory.post(
            reverse("resources:get-compensations", kwargs={"selected_compensation": 1}),
            {
                "resource": self.resource.id,
                "organization": self.organization.id,
                "starttime": "12:00",
                "startdate": "2025-04-28",  # A Monday
            },
        )
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        # The resource should be bookable because the organization is exempt
        assert (
            "This resource is not available at the selected time."
            not in response.content.decode()
        )


class AccessCodeListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a manager user with access to resources
        self.user = UserFactory()
        self.resource = ResourceFactory()
        self.manager = ManagerFactory(user=self.user, resources=[self.resource])
        self.access_code = AccessCodeFactory(access=self.resource.access)
        self.client.force_login(self.user)

    def test_list_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.FOUND
        assert "/accounts/login/" in response.url

    def test_list_view_requires_manager_permission(self):
        # Create a regular non-manager user
        regular_user = UserFactory()
        self.client.force_login(regular_user)
        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_list_view_displays_access_codes(self):
        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.OK
        assert self.access_code.code in response.content.decode()

    def test_list_view_displays_empty_message(self):
        AccessCode.objects.all().delete()
        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.OK
        assert "No access codes found" in response.content.decode()

    def test_list_view_filters_by_code(self):
        # Create another access code with different code but same access
        AccessCodeFactory(code="DIFFERENT", access=self.resource.access)
        response = self.client.get(
            reverse("resources:accesscode-list"), {"code": self.access_code.code}
        )
        assert response.status_code == HTTPStatus.OK
        assert self.access_code.code in response.content.decode()
        assert "DIFFERENT" not in response.content.decode()

    def test_list_view_only_shows_manager_resources(self):
        # Create another resource and access code that manager doesn't have access to
        other_resource = ResourceFactory()
        other_access_code = AccessCodeFactory(access=other_resource.access)

        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.OK
        # Should show the access code for manager's resource
        assert self.access_code.code in response.content.decode()
        # Should NOT show the access code for other resource
        assert other_access_code.code not in response.content.decode()

    def test_list_view_has_filter_in_context(self):
        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.OK
        # Check that the filter is available in the context
        assert "filter" in response.context or "filterset" in response.context

    def test_list_view_filter_only_shows_manager_access_choices(self):
        # Create another resource and access that manager doesn't have access to
        other_resource = ResourceFactory()
        other_access = other_resource.access

        response = self.client.get(reverse("resources:accesscode-list"))
        assert response.status_code == HTTPStatus.OK

        # Get the filterset from context
        filterset = response.context.get("filterset")
        assert filterset is not None

        # Get the queryset of Access choices in the filter
        access_choices = filterset.filters["access"].queryset

        # Manager's access should be in the choices
        assert self.resource.access in access_choices
        # Other access should NOT be in the choices
        assert other_access not in access_choices


class AccessCodeDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.resource = ResourceFactory()
        self.manager = ManagerFactory(user=self.user, resources=[self.resource])
        self.access_code = AccessCodeFactory(access=self.resource.access)
        self.client.force_login(self.user)

    def test_detail_view_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse(
                "resources:accesscode-detail", kwargs={"uuid": self.access_code.uuid}
            )
        )
        assert response.status_code == HTTPStatus.FOUND
        assert "/accounts/login/" in response.url

    def test_detail_view_displays_access_code(self):
        response = self.client.get(
            reverse(
                "resources:accesscode-detail", kwargs={"uuid": self.access_code.uuid}
            )
        )
        assert response.status_code == HTTPStatus.OK
        assert self.access_code.code in response.content.decode()
        assert str(self.access_code.access) in response.content.decode()

    def test_detail_view_404_for_nonexistent_uuid(self):
        response = self.client.get(
            reverse(
                "resources:accesscode-detail",
                kwargs={"uuid": "00000000-0000-0000-0000-000000000000"},
            )
        )
        assert response.status_code == HTTPStatus.NOT_FOUND


class AccessCodeCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.resource = ResourceFactory()
        self.manager = ManagerFactory(user=self.user, resources=[self.resource])
        self.access = self.resource.access
        self.organization = OrganizationFactory()
        self.client.force_login(self.user)

    def test_create_view_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("resources:accesscode-create"))
        assert response.status_code == HTTPStatus.FOUND
        assert "/accounts/login/" in response.url

    def test_create_view_get_displays_form(self):
        response = self.client.get(reverse("resources:accesscode-create"))
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context

    def test_create_view_post_creates_access_code(self):
        initial_count = AccessCode.objects.count()
        response = self.client.post(
            reverse("resources:accesscode-create"),
            {
                "access": self.access.id,
                "code": "TEST123",
                "validity_start": "2025-01-01 12:00:00",
                "organization": self.organization.id,
            },
        )
        assert AccessCode.objects.count() == initial_count + 1
        new_access_code = AccessCode.objects.latest("created")
        assert new_access_code.code == "TEST123"
        assert response.status_code == HTTPStatus.FOUND

    def test_create_view_post_redirects_to_list(self):
        response = self.client.post(
            reverse("resources:accesscode-create"),
            {
                "access": self.access.id,
                "code": "TEST456",
                "validity_start": "2025-01-01 12:00:00",
                "organization": self.organization.id,
            },
            follow=True,
        )
        assert response.redirect_chain[-1][0] == reverse("resources:accesscode-list")

    def test_create_view_post_invalid_data(self):
        initial_count = AccessCode.objects.count()
        response = self.client.post(
            reverse("resources:accesscode-create"),
            {
                "access": "",
                "code": "",
                "validity_start": "invalid-date",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert AccessCode.objects.count() == initial_count
        assert "form" in response.context


class AccessCodeUpdateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.resource = ResourceFactory()
        self.manager = ManagerFactory(user=self.user, resources=[self.resource])
        self.access_code = AccessCodeFactory(access=self.resource.access)
        self.client.force_login(self.user)

    def test_update_view_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse(
                "resources:accesscode-update", kwargs={"uuid": self.access_code.uuid}
            )
        )
        assert response.status_code == HTTPStatus.FOUND
        assert "/accounts/login/" in response.url

    def test_update_view_get_displays_form_with_instance(self):
        response = self.client.get(
            reverse(
                "resources:accesscode-update", kwargs={"uuid": self.access_code.uuid}
            )
        )
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context
        assert response.context["object"] == self.access_code

    def test_update_view_post_updates_access_code(self):
        response = self.client.post(
            reverse(
                "resources:accesscode-update", kwargs={"uuid": self.access_code.uuid}
            ),
            {
                "access": self.access_code.access.id,
                "code": "UPDATED123",
                "validity_start": "2025-01-01 12:00:00",
                "organization": self.access_code.organization.id,
            },
        )
        self.access_code.refresh_from_db()
        assert self.access_code.code == "UPDATED123"
        assert response.status_code == HTTPStatus.FOUND

    def test_update_view_post_redirects_to_list(self):
        response = self.client.post(
            reverse(
                "resources:accesscode-update", kwargs={"uuid": self.access_code.uuid}
            ),
            {
                "access": self.access_code.access.id,
                "code": "UPDATED456",
                "validity_start": "2025-01-01 12:00:00",
                "organization": self.access_code.organization.id,
            },
            follow=True,
        )
        assert response.redirect_chain[-1][0] == reverse("resources:accesscode-list")


class AccessCodeDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory()
        self.resource = ResourceFactory()
        self.manager = ManagerFactory(user=self.user, resources=[self.resource])
        self.access_code = AccessCodeFactory(access=self.resource.access)
        self.client.force_login(self.user)

    def test_delete_view_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse(
                "resources:accesscode-delete", kwargs={"uuid": self.access_code.uuid}
            )
        )
        assert response.status_code == HTTPStatus.FOUND
        assert "/accounts/login/" in response.url

    def test_delete_view_get_displays_confirmation(self):
        response = self.client.get(
            reverse(
                "resources:accesscode-delete", kwargs={"uuid": self.access_code.uuid}
            )
        )
        assert response.status_code == HTTPStatus.OK
        assert self.access_code.code in response.content.decode()

    def test_delete_view_post_deletes_access_code(self):
        access_code_uuid = self.access_code.uuid
        initial_count = AccessCode.objects.count()
        response = self.client.post(
            reverse("resources:accesscode-delete", kwargs={"uuid": access_code_uuid})
        )
        assert AccessCode.objects.count() == initial_count - 1
        assert not AccessCode.objects.filter(uuid=access_code_uuid).exists()
        assert response.status_code == HTTPStatus.FOUND

    def test_delete_view_post_redirects_to_list(self):
        response = self.client.post(
            reverse(
                "resources:accesscode-delete", kwargs={"uuid": self.access_code.uuid}
            ),
            follow=True,
        )
        assert response.redirect_chain[-1][0] == reverse("resources:accesscode-list")


class ResourceIcalFeedTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.resource = ResourceFactory()
        today = timezone.now().date()
        self.today_booking = BookingFactory(resource=self.resource, start_date=today)
        self.future_booking = BookingFactory(
            resource=self.resource, start_date=today + timedelta(days=7)
        )
        self.past_booking = BookingFactory(
            resource=self.resource, start_date=today - timedelta(days=7)
        )

    def test_ical_feed_accessible(self):
        response = self.client.get(
            reverse(
                "resources:daily-calendar", kwargs={"resource_slug": self.resource.slug}
            )
        )
        assert response.status_code == HTTPStatus.OK

    def test_ical_feed_content_type(self):
        response = self.client.get(
            reverse(
                "resources:daily-calendar", kwargs={"resource_slug": self.resource.slug}
            )
        )
        assert response["Content-Type"] == "text/calendar; charset=utf-8"

    def test_ical_feed_includes_today_bookings(self):
        response = self.client.get(
            reverse(
                "resources:daily-calendar", kwargs={"resource_slug": self.resource.slug}
            )
        )
        content = response.content.decode()
        assert self.today_booking.organization.name in content
        assert "BEGIN:VCALENDAR" in content
        assert "BEGIN:VEVENT" in content

    def test_ical_feed_excludes_past_bookings(self):
        response = self.client.get(
            reverse(
                "resources:daily-calendar", kwargs={"resource_slug": self.resource.slug}
            )
        )
        content = response.content.decode()
        # Past booking should not be included
        assert self.past_booking.slug not in content

    def test_ical_feed_has_calendar_metadata(self):
        response = self.client.get(
            reverse(
                "resources:daily-calendar", kwargs={"resource_slug": self.resource.slug}
            )
        )
        content = response.content.decode()
        assert self.resource.name in content
        assert "Booking schedule for" in content
