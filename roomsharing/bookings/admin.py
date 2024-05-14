# Register your models here.
from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    model = Booking
    list_display = ["id", "room", "timespan", "status", "organization", "title", "user"]
    search_fields = ["id", "room", "organization", "title", "user"]
    list_filter = ["status", "organization", "room"]
    ordering = ["id"]
