from collections import defaultdict

from auditlog.context import set_actor
from dateutil.relativedelta import relativedelta
from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportMixin

from re_sharing.bookings.models import Booking
from re_sharing.utils.models import BookingStatus

from .mails import send_monthly_overview_email
from .models import BookingPermission
from .models import EmailTemplate
from .models import Organization
from .models import OrganizationGroup
from .models import OrganizationMessage


@admin.register(Organization)
class OrganizationAdmin(ImportExportMixin, admin.ModelAdmin):
    list_filter = ["status", "organization_groups", "monthly_bulk_access_codes"]
    list_display = [
        "id",
        "name",
        "status",
        "usage_agreement",
        "usage_agreement_date",
        "monthly_bulk_access_codes",
    ]
    search_fields = ["name", "id"]
    ordering = ["-id"]
    actions = [
        "activate_bulk_sending",
        "deactivate_bulk_sending",
        "admin_send_monthly_bookings_overview",
    ]

    @admin.action(description=_("Activate bulk sending"))
    def activate_bulk_sending(self, request, queryset):
        for organization in queryset:
            with set_actor(request.user):
                organization.monthly_bulk_access_codes = True
                organization.save()

    @admin.action(description=_("Deactivate bulk sending"))
    def deactivate_bulk_sending(self, request, queryset):
        for organization in queryset:
            with set_actor(request.user):
                organization.monthly_bulk_access_codes = False
                organization.save()

    @admin.action(description=_("Send monthly bookings overview"))
    def admin_send_monthly_bookings_overview(self, request, queryset):
        # Get next month's date range
        next_month = timezone.now() + relativedelta(months=+1)
        next_month_start = next_month.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        # Get bookings for the selected organizations
        bookings = Booking.objects.filter(
            status=BookingStatus.CONFIRMED,
            organization__in=queryset,
            timespan__startswith__gte=next_month_start,
            timespan__startswith__lt=next_month_start + relativedelta(months=1),
        )

        # Group bookings by organization
        bookings_by_org = defaultdict(list)
        for booking in bookings:
            bookings_by_org[booking.organization].append(booking.id)

        # Enqueue tasks for each organization
        for organization, booking_ids in bookings_by_org.items():
            send_monthly_overview_email.enqueue(
                organization.id,
                booking_ids,
                next_month.isoformat(),
            )


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
    ordering = ["-id"]


@admin.register(OrganizationGroup)
class OrganizationGroupAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["id", "name"]
    list_filter = ["name"]
    ordering = ["-id"]


@admin.register(OrganizationMessage)
class OrganizationMessageAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "organization", "user"]
    list_filter = ["organization"]
    ordering = ["-id"]
