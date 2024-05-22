from django.contrib import admin

from .models import Room
from .models import RoomImage


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    model = Room
    list_display = ["id", "name", "square_meters", "max_persons"]
    search_fields = ["id", "name"]
    ordering = ["id"]


admin.site.register(RoomImage)
