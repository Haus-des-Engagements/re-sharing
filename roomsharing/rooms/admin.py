from django.contrib import admin

from .models import Access
from .models import AccessCode
from .models import Compensation
from .models import Room
from .models import RoomImage


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    model = Room
    list_display = ["id", "name", "square_meters", "max_persons"]
    search_fields = ["id", "name"]
    ordering = ["id"]


admin.site.register(RoomImage)
admin.site.register(Access)
admin.site.register(AccessCode)
admin.site.register(Compensation)
