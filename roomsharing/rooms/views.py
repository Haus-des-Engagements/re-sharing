from django.views.generic import DetailView
from django.views.generic import ListView

from roomsharing.rooms.models import Room


class RoomDetailView(DetailView):
    model = Room
    slug_field = "slug"
    slug_url_kwarg = "slug"


class RoomListView(ListView):
    model = Room
    template_name = "rooms/room_list.html"
    context_object_name = "rooms"
