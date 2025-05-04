from datetime import time
from http import HTTPStatus

import pytest
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
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
        from datetime import datetime

        # Monday at 12:00
        monday_noon = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=28, hour=12, minute=0, second=0, microsecond=0
        )
        assert self.restriction.applies_to_datetime(monday_noon)

    def test_restriction_does_not_apply_to_datetime_weekend(self):
        """
        Test that the restriction does not apply to a datetime on a weekend.
        """
        from datetime import datetime

        # Saturday at 12:00
        saturday_noon = datetime.now(tz=timezone.get_current_timezone()).replace(
            year=2025, month=4, day=26, hour=12, minute=0, second=0, microsecond=0
        )
        assert not self.restriction.applies_to_datetime(saturday_noon)

    def test_restriction_does_not_apply_to_datetime_outside_hours(self):
        """
        Test that the restriction does not apply to a datetime outside the time range.
        """
        from datetime import datetime

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
