from django.contrib import admin
from import_export.admin import ImportExportMixin

from .models import BookingPermission
from .models import EmailTemplate
from .models import Organization
from .models import OrganizationGroup


@admin.register(Organization)
class OrganizationAdmin(ImportExportMixin, admin.ModelAdmin):
    list_filter = ["status", "organization_groups"]
    list_display = ["id", "name", "status", "usage_agreement", "usage_agreement_date"]
    search_fields = ["name", "id"]
    ordering = ["-id"]


@admin.register(EmailTemplate)
class EmailTemplateAdmin(ImportExportMixin, admin.ModelAdmin):
    list_filter = ["email_type", "subject", "active"]
    list_display = ["email_type", "subject", "active"]


@admin.register(BookingPermission)
class BookingPermissionAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "user", "user__email", "organization", "role", "status"]
    search_fields = [
        "organization__id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "organization__name",
        "role",
        "status",
    ]
    list_filter = ["role", "status", "organization"]
    ordering = ["id"]


@admin.register(OrganizationGroup)
class OrganizationGroupAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["id", "name"]
    list_filter = ["name"]
    ordering = ["id"]
