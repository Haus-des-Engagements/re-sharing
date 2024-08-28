# Register your models here.
from django.contrib import admin

from .models import Booking
from .models import BookingMessage
from .models import RecurrenceRule


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    model = Booking
    list_display = ["id", "room", "timespan", "status", "organization", "title", "user"]
    search_fields = ["id", "room", "organization", "title", "user"]
    list_filter = ["status", "organization", "room", "recurrence_rule"]
    ordering = ["id"]


admin.site.register(BookingMessage)
admin.site.register(RecurrenceRule)
