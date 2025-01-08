from http import HTTPStatus

import pytest
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory
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
        self.assertContains(response, self.resource.name)

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


class GetCompensationsViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.resource = ResourceFactory(name="Test Resource")
        self.compensation_name = "For Free"
        self.compensation = CompensationFactory(name=self.compensation_name)
        self.compensation.resource.add(self.resource)

    def test_get_compensations_empty_resource(self):
        request = self.factory.post(reverse("resources:get-compensations"))
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Please select a resource first.", html=True)

    def test_get_compensations_with_resource(self):
        request = self.factory.post(
            reverse("resources:get-compensations"), {"resource": self.resource.id}
        )
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, self.compensation_name)
