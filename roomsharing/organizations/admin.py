from django.contrib import admin
from import_export.admin import ImportExportMixin

from .models import BookingPermission
from .models import EmailTemplate
from .models import Organization
from .models import OrganizationGroup


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


@admin.register(OrganizationGroup)
class OrganizationGroupAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["id", "name"]
    list_filter = ["name"]
    ordering = ["id"]
