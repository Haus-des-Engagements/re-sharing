from http import HTTPStatus

import pytest
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.rooms.views import get_weekly_bookings_view
from roomsharing.rooms.views import list_rooms_view
from roomsharing.rooms.views import show_room_view


class RoomDetailViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.room = RoomFactory()

    def test_room_detail_view(self):
        request = self.factory.get(
            reverse("rooms:show-room", kwargs={"slug": self.room.slug}),
        )
        response = show_room_view(request, slug=self.room.slug)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, self.room.name)


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


class GetWeeklyBookingsViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.room = RoomFactory()

    def test_get_weekly_booking_view(self):
        request = self.factory.get(
            reverse("rooms:get-weekly-bookings", kwargs={"room_slug": self.room.slug}),
        )
        response = get_weekly_bookings_view(request, room_slug=self.room.slug)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Time")
