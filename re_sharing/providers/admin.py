from django.contrib import admin
from import_export.admin import ImportExportMixin

from .models import LendingTimeSlot
from .models import Manager


@admin.register(Manager)
class ManagerAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "user"]
    search_fields = ["id", "user__email", "user__first_name", "user__last_name"]
    filter_horizontal = ["resources", "organization_groups"]
    ordering = ["id"]


@admin.register(LendingTimeSlot)
class LendingTimeSlotAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "slot_type",
        "weekday",
        "start_time",
        "end_time",
        "is_active",
    ]
    list_filter = ["slot_type", "is_active"]
    ordering = ["slot_type", "weekday"]
