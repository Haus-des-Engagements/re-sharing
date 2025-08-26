from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta

from auditlog.context import set_actor
from dateutil.rrule import rrulestr
from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from import_export import fields
from import_export import resources
from import_export.admin import ImportExportMixin
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget

from re_sharing.resources.models import Resource
from re_sharing.utils.models import BookingStatus

from .models import Booking
from .models import BookingMessage
from .models import BookingSeries
from .services_booking_series import generate_bookings
from .services_booking_series import max_future_booking_date


# avoid namespacing problems by renaming resource to booked_resource
class BookingResource(resources.ModelResource):
    booked_resource = fields.Field(
        column_name="resource",
        attribute="resource",
        widget=ForeignKeyWidget(Resource, "id"),
    )

    class Meta:
        model = Booking
        fields = (
            "id",
            "title",
            "booked_resource",
            "organization",
            "user",
            "import_id",
            "booking_series",
            "start_date",
            "start_time",
            "end_date",
            "end_time",
            "timespan",
            "compensation",
            "status",
            "total_amount",
            "activity_description",
            "invoice_number",
            "invoice_address",
            "number_of_attendees",
            "slug",
        )


@admin.register(Booking)
class BookingAdmin(ImportExportModelAdmin):
    list_display = [
        "id",
        "resource",
        "timespan",
        "status",
        "organization",
        "title",
        "user",
        "import_id",
        "compensation",
    ]
    search_fields = ["id", "title", "slug", "import_id", "organization__name"]
    list_filter = [
        "status",
        "organization__organization_groups",
        "resource",
        "compensation",
        "resource__location",
    ]
    ordering = ["id"]
    actions = ["confirm_bookings", "cancel_bookings"]
    resource_classes = [BookingResource]

    @admin.action(description=_("Confirm selected bookings"))
    def confirm_bookings(self, request, queryset):
        for booking in queryset:
            with set_actor(request.user):
                booking.status = BookingStatus.CONFIRMED
                booking.save()
        count = queryset.count()
        self.message_user(
            request,
            ngettext(
                "%d booking was successfully confirmed.",
                "%d bookings were successfully confirmed.",
                count,
            )
            % count,
            messages.SUCCESS,
        )

    @admin.action(description=_("Cancel selected bookings"))
    def cancel_bookings(self, request, queryset):
        for booking in queryset:
            with set_actor(request.user):
                booking.status = BookingStatus.CANCELLED
                booking.save()
        count = queryset.count()
        self.message_user(
            request,
            ngettext(
                "%d booking was successfully cancelled.",
                "%d bookings were successfully cancelled.",
                count,
            )
            % count,
            messages.SUCCESS,
        )


# avoid namespacing problems by renaming resource to booked_resource
class BookingSeriesResource(resources.ModelResource):
    booked_resource = fields.Field(
        column_name="resource",
        attribute="resource",
        widget=ForeignKeyWidget(Resource, "id"),
    )

    class Meta:
        model = BookingSeries
        fields = (
            "id",
            "title",
            "booked_resource",
            "organization",
            "user",
            "import_id",
            "rrule",
            "first_booking_date",
            "start_time",
            "last_booking_date",
            "end_time",
            "compensation",
            "status",
            "total_amount_per_booking",
            "reminder_emails",
            "activity_description",
            "invoice_address",
            "number_of_attendees",
            "slug",
        )


@admin.register(BookingSeries)
class BookingSeriesAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = [
        "created",
        "id",
        "organization",
        "organization__monthly_bulk_access_codes",
        "reminder_emails",
        "user",
        "first_booking_date",
        "last_booking_date",
        "status",
        "booking_count_link",
    ]
    resource_classes = [BookingSeriesResource]
    search_fields = [
        "id",
        "title",
        "slug",
        "import_id",
        "user__first_name",
        "organization__name",
    ]
    list_filter = [
        "organization__monthly_bulk_access_codes",
        "reminder_emails",
        "status",
        "organization__organization_groups",
    ]
    readonly_fields = ["booking_count_link"]
    actions = [
        "generate_bookings",
        "delete_bookings",
        "activate_reminder_mails",
        "deactivate_reminder_mails",
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(booking_count=Count("booking_of_bookingseries"))

    @admin.display(description=_("Bookings"))
    def booking_count_link(self, obj):
        url = (
            reverse("admin:bookings_booking_changelist")
            + f"?booking_series__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, obj.booking_count)

    def save_model(self, request, obj, form, change):
        if change:  # This ensures we're modifying an existing record
            # Organization has changed. Update related bookings.
            previous = BookingSeries.objects.get(pk=obj.pk)
            bookings = Booking.objects.filter(booking_series=obj)

            for booking in bookings:
                booking.organization = obj.organization
                booking.user = obj.user
                booking.compensation = obj.compensation
                booking.total_amount = obj.total_amount_per_booking
                booking.title = obj.title
            Booking.objects.bulk_update(
                bookings,
                ["organization", "user", "compensation", "total_amount", "title"],
            )

            if previous.rrule != obj.rrule:
                if "COUNT" not in obj.rrule and "UNTIL" not in obj.rrule:
                    obj.last_booking_date = None
                else:
                    obj.last_booking_date = list(rrulestr(obj.rrule))[-1]

        super().save_model(request, obj, form, change)

    @admin.action(description=_("Generate bookings"))
    def generate_bookings(self, request, queryset):
        for booking_series in queryset:
            with set_actor(request.user):
                max_booking_date = timezone.now().date() + timedelta(
                    days=max_future_booking_date
                )
                start_new_bookings_at = timezone.now()

                last_second = time(hour=23, minute=59, second=59)
                end_new_bookings_at = datetime.combine(
                    max_booking_date, last_second
                ).astimezone(UTC)
                bookings = generate_bookings(
                    booking_series, start_new_bookings_at, end_new_bookings_at
                )
                for current_booking in bookings:
                    # Determine if the current booking stems from the same rrule and
                    # thus should not be saved
                    is_same_booking_series = (
                        current_booking.status == BookingStatus.UNAVAILABLE
                        and Booking.objects.filter(resource=booking_series.resource)
                        .filter(timespan__overlap=current_booking.timespan)
                        .filter(booking_series=booking_series)
                        .exists()
                    )
                    if not is_same_booking_series:
                        current_booking.save()

    @admin.action(description=_("Delete bookings"))
    def delete_bookings(self, request, queryset):
        for booking_series in queryset:
            with set_actor(request.user):
                Booking.objects.filter(booking_series=booking_series).delete()

    @admin.action(description=_("Activate reminder mails"))
    def activate_reminder_mails(self, request, queryset):
        for booking_series in queryset:
            with set_actor(request.user):
                booking_series.reminder_emails = True
                booking_series.save()

    @admin.action(description=_("Deactivate reminder mails"))
    def deactivate_reminder_mails(self, request, queryset):
        for booking_series in queryset:
            with set_actor(request.user):
                booking_series.reminder_emails = False
                booking_series.save()


@admin.register(BookingMessage)
class BookingMessageAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "user", "booking"]
    search_fields = ["id", "user", "booking"]
    ordering = ["id"]
