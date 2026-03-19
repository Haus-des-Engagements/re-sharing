from datetime import datetime
from datetime import time
from datetime import timedelta
from http import HTTPStatus
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import LocationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.resources.tests.factories import ResourceRestrictionFactory
from re_sharing.resources.views import get_compensations
from re_sharing.resources.views import list_resources_view
from re_sharing.resources.views import planner_view
from re_sharing.resources.views import show_resource_view
from re_sharing.users.tests.factories import UserFactory


def make_test_image(name="test.jpg"):
    """Return a SimpleUploadedFile with a minimal JPEG."""
    buf = BytesIO()
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type="image/jpeg")


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


# ---------------------------------------------------------------------------
# Manager resource views
# ---------------------------------------------------------------------------


class TestManagerListResourcesView(TestCase):
    URL = "resources:manager-list-resources"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)

        self.location1 = LocationFactory()
        self.location2 = LocationFactory()

        self.room = ResourceFactory(
            type=Resource.ResourceTypeChoices.ROOM,
            location=self.location1,
        )
        self.item = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            location=self.location2,
            quantity_available=5,
        )

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(reverse(self.URL))
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_manager_can_access(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        assert response.status_code == HTTPStatus.OK

    def test_shows_all_resources_by_default(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        pks = [r.pk for r in response.context["resources"]]
        assert self.room.pk in pks
        assert self.item.pk in pks

    def test_filter_by_type(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL), {"type": "lendable_item"})
        pks = [r.pk for r in response.context["resources"]]
        assert self.item.pk in pks
        assert self.room.pk not in pks

    def test_filter_by_location(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL), {"location": self.location1.slug})
        pks = [r.pk for r in response.context["resources"]]
        assert self.room.pk in pks
        assert self.item.pk not in pks

    def test_locations_in_context(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL))
        location_pks = [loc.pk for loc in response.context["locations"]]
        assert self.location1.pk in location_pks
        assert self.location2.pk in location_pks

    def test_htmx_returns_partial(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(reverse(self.URL), headers={"hx-request": "true"})
        assert response.status_code == HTTPStatus.OK


class TestManagerShowResourceView(TestCase):
    URL = "resources:manager-show-resource"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)

        self.resource = ResourceFactory(
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            quantity_available=3,
        )
        self.compensation = CompensationFactory(
            resource=[self.resource],
            daily_rate=10,
        )

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(
            reverse(self.URL, kwargs={"resource_slug": self.resource.slug})
        )
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_shows_resource(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(
            reverse(self.URL, kwargs={"resource_slug": self.resource.slug})
        )
        assert response.status_code == HTTPStatus.OK
        assert response.context["resource"] == self.resource

    def test_shows_compensations(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(
            reverse(self.URL, kwargs={"resource_slug": self.resource.slug})
        )
        assert self.compensation in response.context["compensations"]

    def test_shows_images(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(
            reverse(self.URL, kwargs={"resource_slug": self.resource.slug})
        )
        assert "images" in response.context

    def test_image_upload_form_in_context(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(
            reverse(self.URL, kwargs={"resource_slug": self.resource.slug})
        )
        assert "image_form" in response.context


class TestManagerEditCompensationView(TestCase):
    URL = "resources:manager-edit-compensation"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)

        self.resource = ResourceFactory(type=Resource.ResourceTypeChoices.LENDABLE_ITEM)
        self.compensation = CompensationFactory(
            resource=[self.resource],
            name="Old Name",
            conditions="Old conditions",
            hourly_rate=None,
            daily_rate=10,
        )

    def _url(self):
        return reverse(
            self.URL,
            kwargs={
                "compensation_id": self.compensation.pk,
            },
        )

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(self._url())
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_get_shows_form(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self._url())
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].instance == self.compensation

    def test_shows_affected_resources_warning(self):
        """Edit page lists all resources linked to this compensation."""
        other_resource = ResourceFactory()
        self.compensation.resource.add(other_resource)
        self.client.force_login(self.manager_user)
        response = self.client.get(self._url())
        assert other_resource in response.context["affected_resources"]

    def test_post_updates_compensation(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self._url(),
            data={
                "name": "Updated Name",
                "conditions": "New conditions",
                "daily_rate": "15.00",
                "is_active": True,
            },
        )
        assert response.status_code == HTTPStatus.FOUND
        self.compensation.refresh_from_db()
        assert self.compensation.name == "Updated Name"
        assert str(self.compensation.daily_rate) == "15.00"

    def test_invalid_post_shows_form_again(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(self._url(), data={"name": ""})
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context


class TestManagerLinkCompensationView(TestCase):
    """Linking an existing compensation to a resource."""

    URL = "resources:manager-link-compensation"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.resource = ResourceFactory()
        self.compensation = CompensationFactory()  # not yet linked

    def _url(self):
        return reverse(self.URL, kwargs={"resource_slug": self.resource.slug})

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(
            self._url(), data={"compensation_id": self.compensation.pk}
        )
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_links_compensation_to_resource(self):
        self.client.force_login(self.manager_user)
        self.client.post(self._url(), data={"compensation_id": self.compensation.pk})
        assert self.resource.compensations_of_resource.filter(
            pk=self.compensation.pk
        ).exists()

    def test_redirects_to_detail(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self._url(), data={"compensation_id": self.compensation.pk}
        )
        assert response.status_code == HTTPStatus.FOUND
        assert (
            reverse(
                "resources:manager-show-resource",
                kwargs={"resource_slug": self.resource.slug},
            )
            in response["Location"]
        )

    def test_detail_view_lists_unlinked_compensations(self):
        """Unlinked compensations appear in the 'add existing' dropdown context."""
        self.client.force_login(self.manager_user)
        response = self.client.get(
            reverse(
                "resources:manager-show-resource",
                kwargs={"resource_slug": self.resource.slug},
            )
        )
        assert self.compensation in response.context["available_compensations"]


class TestManagerUnlinkCompensationView(TestCase):
    """Removing a compensation from a resource without deleting it."""

    URL = "resources:manager-unlink-compensation"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.resource = ResourceFactory()
        self.compensation = CompensationFactory(resource=[self.resource])

    def _url(self):
        return reverse(
            self.URL,
            kwargs={
                "resource_slug": self.resource.slug,
                "compensation_id": self.compensation.pk,
            },
        )

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(self._url())
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_removes_link_but_keeps_compensation(self):
        self.client.force_login(self.manager_user)
        self.client.post(self._url())
        # compensation still exists
        self.compensation.refresh_from_db()
        assert self.compensation.pk is not None
        # but no longer linked to this resource
        assert not self.resource.compensations_of_resource.filter(
            pk=self.compensation.pk
        ).exists()

    def test_redirects_to_detail(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(self._url())
        assert response.status_code == HTTPStatus.FOUND
        assert (
            reverse(
                "resources:manager-show-resource",
                kwargs={"resource_slug": self.resource.slug},
            )
            in response["Location"]
        )


class TestManagerCreateCompensationView(TestCase):
    """Creating a new compensation and linking it directly to a resource."""

    URL = "resources:manager-create-compensation"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.resource = ResourceFactory()

    def _url(self):
        return reverse(self.URL, kwargs={"resource_slug": self.resource.slug})

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(self._url())
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_get_shows_empty_form(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self._url())
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context

    def test_post_creates_and_links_compensation(self):
        self.client.force_login(self.manager_user)
        self.client.post(
            self._url(),
            data={
                "name": "New Comp",
                "conditions": "",
                "daily_rate": "5.00",
                "is_active": True,
            },
        )
        assert self.resource.compensations_of_resource.filter(name="New Comp").exists()

    def test_post_redirects_to_detail(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self._url(),
            data={
                "name": "New Comp",
                "conditions": "",
                "daily_rate": "5.00",
                "is_active": True,
            },
        )
        assert response.status_code == HTTPStatus.FOUND
        assert (
            reverse(
                "resources:manager-show-resource",
                kwargs={"resource_slug": self.resource.slug},
            )
            in response["Location"]
        )


class TestManagerEditResourceView(TestCase):
    URL = "resources:manager-edit-resource"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.location = LocationFactory()
        self.resource = ResourceFactory(
            name="Old Name",
            type=Resource.ResourceTypeChoices.LENDABLE_ITEM,
            location=self.location,
            is_private=False,
            quantity_available=2,
        )

    def _url(self):
        return reverse(self.URL, kwargs={"resource_slug": self.resource.slug})

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(self._url())
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_get_shows_form_with_instance(self):
        self.client.force_login(self.manager_user)
        response = self.client.get(self._url())
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context
        assert response.context["form"].instance == self.resource

    def test_post_updates_resource(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self._url(),
            data={
                "name": "New Name",
                "type": Resource.ResourceTypeChoices.LENDABLE_ITEM,
                "location": self.location.pk,
                "is_private": True,
                "quantity_available": 5,
            },
        )
        assert response.status_code == HTTPStatus.FOUND
        self.resource.refresh_from_db()
        assert self.resource.name == "New Name"
        assert self.resource.is_private is True
        assert self.resource.quantity_available == 5  # noqa: PLR2004

    def test_post_redirects_to_detail(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self._url(),
            data={
                "name": "New Name",
                "type": Resource.ResourceTypeChoices.LENDABLE_ITEM,
                "location": self.location.pk,
                "is_private": False,
                "quantity_available": 1,
            },
        )
        assert response.status_code == HTTPStatus.FOUND
        # slug may have changed, so just check it's a resource detail URL
        assert "/manager/" in response["Location"]

    def test_invalid_post_shows_form_again(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(self._url(), data={"name": ""})
        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context


class TestManagerAddResourceImageView(TestCase):
    URL = "resources:manager-add-resource-image"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.resource = ResourceFactory()

    def _url(self):
        return reverse(self.URL, kwargs={"resource_slug": self.resource.slug})

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(
            self._url(), data={"image": make_test_image(), "description": ""}
        )
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_upload_creates_image(self):
        self.client.force_login(self.manager_user)
        self.client.post(
            self._url(), data={"image": make_test_image(), "description": "Test"}
        )
        assert self.resource.resourceimages_of_resource.count() == 1
        assert self.resource.resourceimages_of_resource.first().description == "Test"

    def test_redirects_to_detail_after_upload(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(
            self._url(), data={"image": make_test_image(), "description": ""}
        )
        assert response.status_code == HTTPStatus.FOUND
        assert (
            reverse(
                "resources:manager-show-resource",
                kwargs={"resource_slug": self.resource.slug},
            )
            in response["Location"]
        )


class TestManagerDeleteResourceImageView(TestCase):
    URL = "resources:manager-delete-resource-image"

    def setUp(self):
        self.client = Client()
        self.manager_user = UserFactory()
        ManagerFactory(user=self.manager_user)
        self.resource = ResourceFactory()

        from re_sharing.resources.models import ResourceImage

        buf = BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="JPEG")
        buf.seek(0)
        self.image = ResourceImage.objects.create(
            resource=self.resource,
            image=SimpleUploadedFile("img.jpg", buf.read(), content_type="image/jpeg"),
            description="To delete",
        )

    def _url(self):
        return reverse(
            self.URL,
            kwargs={"resource_slug": self.resource.slug, "image_id": self.image.pk},
        )

    def test_requires_manager(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(self._url())
        assert response.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.FOUND)

    def test_delete_removes_image(self):
        self.client.force_login(self.manager_user)
        self.client.post(self._url())
        assert not self.resource.resourceimages_of_resource.filter(
            pk=self.image.pk
        ).exists()

    def test_redirects_to_detail_after_delete(self):
        self.client.force_login(self.manager_user)
        response = self.client.post(self._url())
        assert response.status_code == HTTPStatus.FOUND
        assert (
            reverse(
                "resources:manager-show-resource",
                kwargs={"resource_slug": self.resource.slug},
            )
            in response["Location"]
        )
