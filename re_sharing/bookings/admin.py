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
from import_export.admin import ImportExportMixin

from re_sharing.utils.models import BookingStatus

from .models import Booking
from .models import BookingMessage
from .models import BookingSeries
from .services_recurrences import generate_bookings
from .services_recurrences import max_future_booking_date


@admin.register(Booking)
class BookingAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "resource",
        "timespan",
        "status",
        "organization",
        "title",
        "user",
    ]
    search_fields = ["id", "title", "slug"]
    list_filter = ["status", "organization", "resource", "booking_series"]
    ordering = ["id"]
    actions = ["confirm_bookings", "cancel_bookings"]

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


@admin.register(BookingSeries)
class RecurrenceRuleAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = [
        "created",
        "id",
        "uuid",
        "organization",
        "first_booking_date",
        "last_booking_date",
        "status",
        "get_first_booking",
        "booking_count_link",
    ]
    list_filter = ["status", "organization"]
    readonly_fields = ["booking_count_link"]
    actions = ["generate_bookings", "delete_bookings"]

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
            Booking.objects.bulk_update(bookings, ["organization"])

            if previous.rrule != obj.rrule:
                if "COUNT" not in obj.rrule and "UNTIL" not in obj.rrule:
                    obj.last_booking_date = None
                else:
                    obj.last_occurrence_date = list(rrulestr(obj.rrule))[-1]

        super().save_model(request, obj, form, change)

    @admin.action(description=_("Generate bookings"))
    def generate_bookings(self, request, queryset):
        for rrule in queryset:
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
                    rrule, start_new_bookings_at, end_new_bookings_at
                )
                for current_booking in bookings:
                    # Determine if the current booking stems from the same rrule and
                    # thus should not be saved
                    is_same_rrule_booking = (
                        current_booking.status == BookingStatus.UNAVAILABLE
                        and Booking.objects.filter(resource=rrule.resource)
                        .filter(timespan__overlap=current_booking.timespan)
                        .filter(booking_series=rrule)
                        .exists()
                    )
                    if not is_same_rrule_booking:
                        current_booking.save()

    @admin.action(description=_("Delete bookings"))
    def delete_bookings(self, request, queryset):
        for rrule in queryset:
            with set_actor(request.user):
                Booking.objects.filter(booking_series=rrule).delete()


@admin.register(BookingMessage)
class BookingMessageAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "user", "booking"]
    search_fields = ["id", "user", "booking"]
    ordering = ["id"]
