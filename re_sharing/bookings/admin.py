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

from re_sharing.organizations.models import Organization
from re_sharing.resources.models import Resource
from re_sharing.utils.models import BookingStatus

from .models import Booking
from .models import BookingMessage
from .models import BookingSeries
from .services_booking_series import generate_bookings
from .services_booking_series import max_future_booking_date


# avoid namespacing problems by renaming resource to booked_resource
class BookingResource(resources.ModelResource):
    def before_import(self, dataset, **kwargs):
        # mimic a 'dynamic field' - i.e. append field which exists on
        # Book model, but not in dataset
        dataset.headers.append("timespan")
        dataset.headers.append("user")
        super().before_import(dataset, **kwargs)

    def before_import_row(self, row, **kwargs):
        row["start_date"] = datetime.strptime(row["start_date"], "%Y-%m-%d").date()  # noqa: DTZ007
        row["start_time"] = datetime.strptime(row["start_time"], "%H:%M").time()  # noqa: DTZ007
        row["end_date"] = datetime.strptime(row["end_date"], "%Y-%m-%d").date()  # noqa: DTZ007
        row["end_time"] = datetime.strptime(row["end_time"], "%H:%M").time()  # noqa: DTZ007

        start = timezone.make_aware(
            datetime.combine(row["start_date"], row["start_time"])
        ).astimezone(UTC)
        end = timezone.make_aware(
            datetime.combine(row["end_date"], row["end_time"])
        ).astimezone(UTC)
        row["timespan"] = [start, end]

        organization = Organization.objects.get(id=row["organization"])
        confirmed_admins = organization.get_confirmed_admins()
        if confirmed_admins.exists():
            user = confirmed_admins.first()
            user = user.id
        else:
            user = 1
        row["user"] = user

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
    ]
    search_fields = ["id", "title", "slug", "import_id"]
    list_filter = ["status", "organization", "resource", "booking_series"]
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
        "user",
        "first_booking_date",
        "last_booking_date",
        "status",
        "get_first_booking",
        "booking_count_link",
        "import_id",
    ]
    resource_classes = [BookingSeriesResource]
    search_fields = ["id", "title", "slug", "import_id", "user", "organization"]
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
                booking.user = obj.user
            Booking.objects.bulk_update(bookings, ["organization", "user"])

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


@admin.register(BookingMessage)
class BookingMessageAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ["id", "user", "booking"]
    search_fields = ["id", "user", "booking"]
    ordering = ["id"]
