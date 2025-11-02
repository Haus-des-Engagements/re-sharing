from django.contrib import admin
from import_export.admin import ImportExportMixin

from .models import Access
from .models import AccessCode
from .models import Compensation
from .models import Location
from .models import Resource
from .models import ResourceImage
from .models import ResourceRestriction


@admin.register(Resource)
class ResourceAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "square_meters", "max_persons", "type", "location"]
    search_fields = ["id", "name"]
    ordering = ["id"]


@admin.register(Compensation)
class CompensationAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "conditions", "hourly_rate"]
    search_fields = ["id", "name"]
    ordering = ["id"]


@admin.register(AccessCode)
class AccessCodeAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "access", "code", "validity_start", "organization"]
    search_fields = ["id", "access", "code"]
    list_filter = ["access", "organization"]
    ordering = ["id"]


@admin.register(Access)
class AccessAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "slug"]
    search_fields = ["id", "name", "slug"]
    ordering = ["id"]


@admin.register(Location)
class LocationAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name", "address"]
    search_fields = ["id", "name", "address"]
    ordering = ["id"]


admin.site.register(ResourceImage)


@admin.register(ResourceRestriction)
class ResourceRestrictionAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "message",
        "start_date",
        "end_date",
        "start_time",
        "end_time",
        "days_of_week",
        "is_active",
    ]
    list_filter = ["is_active", "start_date", "end_date"]
    search_fields = ["id", "message"]
    filter_horizontal = ["resources", "exempt_organization_groups"]
    ordering = ["id"]
    fieldsets = (
        (
            "Date Range",
            {
                "fields": ("start_date", "end_date"),
                "description": (
                    "Define the date range for this restriction. "
                    "Leave both empty to apply always. "
                    "Set only start_date to apply from that date onwards."
                ),
            },
        ),
        (
            "Time and Days",
            {
                "fields": ("start_time", "end_time", "days_of_week"),
            },
        ),
        (
            "Resources and Exemptions",
            {
                "fields": ("resources", "exempt_organization_groups"),
            },
        ),
        (
            "Details",
            {
                "fields": ("message", "is_active"),
            },
        ),
    )
