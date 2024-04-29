# Register your models here.
from django.contrib import admin

from .models import Booking
from .models import BookingGroup
from .models import RecurrencePattern


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    model = Booking
    list_display = ["id", "room", "timespan", "booking_group", "uuid"]
    search_fields = ["id", "room", "booking_group", "uuid"]
    ordering = ["id"]


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0


@admin.register(BookingGroup)
class BookingGroupAdmin(admin.ModelAdmin):
    model = BookingGroup
    list_display = ["id", "title", "organization", "user"]
    search_fields = ["id", "title", "organization", "user"]
    ordering = ["id"]
    inlines = [BookingInline]


admin.site.register(RecurrencePattern)
