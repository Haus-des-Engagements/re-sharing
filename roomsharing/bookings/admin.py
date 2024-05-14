# Register your models here.
from django.contrib import admin

from .models import Booking
from .models import RecurrencePattern


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    model = Booking
    list_display = ["id", "title", "organization", "user", "room", "timespan", "uuid"]
    search_fields = ["id", "title", "organization", "user", "room", "timespan", "uuid"]
    ordering = ["id"]


admin.site.register(RecurrencePattern)
