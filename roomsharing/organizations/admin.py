from django.contrib import admin
from import_export.admin import ImportExportMixin

from .models import BookingPermission
from .models import DefaultBookingStatus
from .models import EmailTemplate
from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(ImportExportMixin, admin.ModelAdmin):
    list_filter = ["status"]


@admin.register(EmailTemplate)
class EmailTemplateAdmin(ImportExportMixin, admin.ModelAdmin):
    list_filter = ["email_type"]


@admin.register(BookingPermission)
class BookingPermissionAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "user", "organization", "role", "status"]
    search_fields = ["id", "user", "organization", "role", "status"]
    list_filter = ["user", "organization", "role", "status"]
    ordering = ["id"]


@admin.register(DefaultBookingStatus)
class DefaultBookingStatusAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "organization", "status"]
    search_fields = ["id", "organization", "room", "status"]
    list_filter = ["organization", "room", "status"]
    ordering = ["id"]
