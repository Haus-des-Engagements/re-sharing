# Register your models here.

from auditlog.context import set_actor
from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from roomsharing.utils.models import BookingStatus

from .models import Booking
from .models import BookingMessage
from .models import RecurrenceRule


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    model = Booking
    list_display = ["id", "room", "timespan", "status", "organization", "title", "user"]
    search_fields = ["id", "title"]
    list_filter = ["status", "organization", "room", "recurrence_rule"]
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


@admin.register(RecurrenceRule)
class RecurrenceRuleAdmin(admin.ModelAdmin):
    model = RecurrenceRule
    list_display = [
        "created",
        "id",
        "uuid",
        "organization",
        "first_occurrence_date",
        "last_occurrence_date",
        "status",
        "get_first_booking",
    ]
    list_filter = ["status", "organization"]

    def save_model(self, request, obj, form, change):
        if change:  # This ensures we're modifying an existing record
            previous = RecurrenceRule.objects.get(pk=obj.pk)
            if previous.organization != obj.organization:
                # Organization has changed. Update related bookings.
                bookings = Booking.objects.filter(recurrence_rule=obj)
                for booking in bookings:
                    booking.organization = obj.organization
                Booking.objects.bulk_update(bookings, ["organization"])

        super().save_model(request, obj, form, change)


admin.site.register(BookingMessage)
