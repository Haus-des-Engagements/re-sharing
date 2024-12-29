from http import HTTPStatus

import pytest
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import RoomFactory
from re_sharing.resources.views import get_compensations
from re_sharing.resources.views import list_rooms_view
from re_sharing.resources.views import planner_view
from re_sharing.resources.views import show_room_view


class ShowRoomViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.room = RoomFactory()

    def test_show_room_view(self):
        request = self.factory.get(
            reverse("rooms:show-room", kwargs={"room_slug": self.room.slug}),
        )
        response = show_room_view(request, room_slug=self.room.slug)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, self.room.name)

    @pytest.mark.django_db()
    def test_show_room_view_hx_request(self):
        # Send GET request to the view with 'HX-Request' in headers
        request = self.factory.get(
            reverse("rooms:show-room", kwargs={"room_slug": self.room.slug}),
            HTTP_HX_REQUEST="true",
        )
        response = show_room_view(request, room_slug=self.room.slug)

        # Check status code of the response
        assert response.status_code == HTTPStatus.OK


class RoomListViewTest(TestCase):
    def setUp(self):
        self.room1 = RoomFactory(slug="green")
        self.room2 = RoomFactory(slug="blue")
        self.factory = RequestFactory()

    def test_room_list_view(self):
        request = self.factory.get(reverse("rooms:list-rooms"))
        response = list_rooms_view(request)
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.django_db()
    def test_list_rooms_view_hx_request(self):
        # Send GET request to the view with 'HX-Request' in headers
        request = self.factory.get(reverse("rooms:list-rooms"), HTTP_HX_REQUEST="true")
        response = list_rooms_view(request)

        # Check status code of the response
        assert response.status_code == HTTPStatus.OK


class PlannerViewTest(TestCase):
    def setUp(self):
        self.room1 = RoomFactory(slug="green")
        self.room2 = RoomFactory(slug="blue")
        self.factory = RequestFactory()

    def test_planner_view(self):
        request = self.factory.get(reverse("rooms:planner"))
        response = planner_view(request)
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.django_db()
    def test_planner_view_hx_request(self):
        # Send GET request to the view with 'HX-Request' in headers
        request = self.factory.get(reverse("rooms:planner"), HTTP_HX_REQUEST="true")
        response = planner_view(request)

        # Check status code of the response
        assert response.status_code == HTTPStatus.OK


class GetCompensationsViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.room = RoomFactory(name="Test Resource")
        self.compensation_name = "For Free"
        self.compensation = CompensationFactory(name=self.compensation_name)
        self.compensation.room.add(self.room)

    def test_get_compensations_empty_room(self):
        request = self.factory.post(reverse("rooms:get-compensations"))
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Please select a room first.", html=True)

    def test_get_compensations_with_room(self):
        request = self.factory.post(
            reverse("rooms:get-compensations"), {"room": self.room.id}
        )
        response = get_compensations(request)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, self.compensation_name)
