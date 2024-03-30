from http import HTTPStatus

from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.rooms.views import RoomDetailView
from roomsharing.rooms.views import RoomListView


class RoomDetailViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.room = RoomFactory()

    def test_room_detail_view(self):
        request = self.factory.get(
            reverse("rooms:detail", kwargs={"slug": self.room.slug}),
        )
        response = RoomDetailView.as_view()(request, slug=self.room.slug)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, self.room.name)


class RoomListViewTest(TestCase):
    def setUp(self):
        self.room1 = RoomFactory(slug="green")
        self.room2 = RoomFactory(slug="blue")
        self.factory = RequestFactory()

    def test_room_list_view(self):
        request = self.factory.get(reverse("rooms:list"))
        response = RoomListView.as_view()(request)
        assert response.status_code == HTTPStatus.OK
