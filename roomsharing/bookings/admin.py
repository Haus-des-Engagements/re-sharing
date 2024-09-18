# Register your models here.
from datetime import timedelta

from auditlog.context import set_actor
from django.contrib import admin
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from django_q.models import Schedule
from django_q.tasks import async_task
from django_q.tasks import schedule

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
            async_task(
                "roomsharing.bookings.tasks.booking_confirmation_email",
                booking,
                task_name="booking-confirmation-email",
            )
            schedule(
                "roomsharing.bookings.tasks.booking_reminder_email",
                booking_slug=booking.slug,
                task_name="booking-reminder-email",
                schedule_type=Schedule.ONCE,
                next_run=booking.timespan.lower - timedelta(days=7),
            )
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


admin.site.register(BookingMessage)
admin.site.register(RecurrenceRule)
