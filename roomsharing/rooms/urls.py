from django.urls import path

from .views import get_compensations
from .views import list_rooms_view
from .views import planner_view
from .views import show_room_view

app_name = "rooms"
urlpatterns = [
    path("", list_rooms_view, name="list-rooms"),
    path("get-compensations/", get_compensations, name="get-compensations"),
    path("planner/", planner_view, name="planner"),
    path("<slug:room_slug>/", show_room_view, name="show-room"),
]
