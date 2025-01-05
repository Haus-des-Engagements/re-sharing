from datetime import datetime
from datetime import time
from datetime import timedelta
from http import HTTPStatus

from auditlog.context import set_actor
from dateutil import parser
from dateutil.parser import isoparse
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_list_or_404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_q.tasks import async_task

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingMessage
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services_booking_series import create_rrule
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.services import get_access_code
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import get_booking_status


class InvalidBookingOperationError(Exception):
    def __init__(self):
        self.message = "You cannot perform this action."
        self.status_code = HTTPStatus.BAD_REQUEST


def set_initial_booking_data(endtime, startdate, starttime, resource):
    initial_data = {}
    if startdate:
        initial_data["startdate"] = startdate
    else:
        initial_data["startdate"] = datetime.strftime(timezone.now().date(), "%Y-%m-%d")
    if starttime:
        initial_data["starttime"] = starttime
        starttime = datetime.strptime(starttime, "%H:%M").astimezone(
            timezone.get_current_timezone()
        )
    else:
        starttime = timezone.localtime(timezone.now()) + timedelta(hours=1)
        initial_data["starttime"] = datetime.strftime(starttime, "%H:00")
    if endtime:
        initial_data["endtime"] = endtime
    else:
        endtime = starttime + timedelta(hours=1)
        initial_data["endtime"] = datetime.strftime(endtime, "%H:00")
    if resource:
        initial_data["resource"] = get_object_or_404(Resource, slug=resource)
    return initial_data


def create_booking_data(user, form):
    if isinstance(form.cleaned_data["timespan"], tuple):
        start, end = form.cleaned_data["timespan"]
        timespan = (start.isoformat(), end.isoformat())

    booking_data = {
        "title": form.cleaned_data["title"],
        "resource": form.cleaned_data["resource"].slug,
        "timespan": timespan,
        "organization": form.cleaned_data["organization"].slug,
        "start_date": form.cleaned_data["startdate"].isoformat(),
        "end_date": form.cleaned_data["enddate"].isoformat(),
        "start_time": form.cleaned_data["starttime"].isoformat(),
        "end_time": form.cleaned_data["endtime"].isoformat(),
        "user": user.slug,
        "compensation": form.cleaned_data["compensation"].id,
        "invoice_address": form.cleaned_data["invoice_address"],
        "activity_description": form.cleaned_data["activity_description"],
        "import_id": form.cleaned_data["import_id"],
    }
    rrule = None
    if form.cleaned_data["rrule_repetitions"] != "NO_REPETITIONS":
        rrule = create_rrule(form.cleaned_data)
        booking_data["rrule_string"] = rrule

    return booking_data, rrule


def generate_booking(booking_data):
    timespan = (
        isoparse(booking_data["timespan"][0]),
        isoparse(booking_data["timespan"][1]),
    )
    organization = get_object_or_404(Organization, slug=booking_data["organization"])
    resource = get_object_or_404(Resource, slug=booking_data["resource"])

    start = timespan[0]
    end = timespan[1]
    compensation = None
    total_amount = None
    if booking_data["compensation"] != "":
        compensation = get_object_or_404(Compensation, id=booking_data["compensation"])
        if compensation.hourly_rate is not None:
            total_amount = (
                (end - start).total_seconds() / 3600 * compensation.hourly_rate
            )

    user = get_object_or_404(User, slug=booking_data["user"])

    return Booking(
        user=user,
        title=booking_data["title"],
        resource=resource,
        organization=organization,
        status=get_booking_status(user, organization, resource),
        timespan=timespan,
        start_date=booking_data["start_date"],
        end_date=booking_data["end_date"],
        start_time=booking_data["start_time"],
        end_time=booking_data["end_time"],
        compensation=compensation,
        total_amount=total_amount,
        invoice_address=booking_data["invoice_address"],
        activity_description=booking_data["activity_description"],
        import_id=booking_data["import_id"],
    )


def save_booking(user, booking):
    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    booking.save()

    # re-retrieve booking object, to be able to call timespan.lower
    booking.refresh_from_db()
    if booking.status == BookingStatus.CONFIRMED:
        async_task(
            "re_sharing.organizations.mails.booking_confirmation_email",
            booking,
            task_name="booking-confirmation-email",
        )
    if booking.status == BookingStatus.PENDING:
        async_task(
            "re_sharing.organizations.mails.manager_new_booking",
            booking,
            task_name="manager-new-booking",
        )

    return booking


def show_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    activity_stream = get_booking_activity_stream(booking)

    access_code = get_access_code(
        booking.resource.slug, booking.organization.slug, booking.timespan.lower
    )

    if access_code and booking.status in [
        BookingStatus.PENDING,
        BookingStatus.CANCELLED,
    ]:
        access_code = _("only shown when confirmed")
    elif access_code and booking.status == BookingStatus.CONFIRMED:
        access_code = access_code.code
    else:
        access_code = "not necessary"

    return booking, activity_stream, access_code


def save_bookingmessage(booking, message, user):
    booking_message = BookingMessage(
        booking=booking,
        text=message,
        user=user,
    )
    booking_message.save()
    async_task(
        "re_sharing.organizations.mails.new_booking_message_email",
        booking_message,
        task_name="new-booking-message-email",
    )
    return booking_message


def create_bookingmessage(booking_slug, form, user):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    if form.is_valid():
        message = form.cleaned_data["text"]
        return save_bookingmessage(booking, message, user)

    raise InvalidBookingOperationError


def cancel_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    if booking.is_cancelable():
        with set_actor(user):
            booking.status = BookingStatus.CANCELLED
            booking.save()

        return booking

    raise InvalidBookingOperationError


def get_booking_activity_stream(booking):
    activity_stream = []
    booking_logs = booking.history.filter(changes__has_key="status").exclude(
        changes__status__contains="None"
    )
    for log_entry in booking_logs:
        status_integer_old = int(log_entry.changes["status"][0])
        status_text_old = dict(BookingStatus.choices).get(status_integer_old)

        status_integer_new = int(log_entry.changes["status"][1])
        status_text_new = dict(BookingStatus.choices).get(status_integer_new)
        status_change_dict = {
            "date": log_entry.timestamp,
            "type": "status_change",
            "old_status": [status_integer_old, status_text_old],
            "new_status": [status_integer_new, status_text_new],
            "user": get_object_or_404(User, id=log_entry.actor_id),
        }
        activity_stream.append(status_change_dict)
    messages = BookingMessage.objects.filter(booking=booking)
    for message in messages:
        message_dict = {
            "date": message.created,
            "type": "message",
            "text": message.text,
            "user": message.user,
        }
        activity_stream.append(message_dict)
    return sorted(activity_stream, key=lambda x: x["date"], reverse=True)


def filter_bookings_list(  # noqa: PLR0913
    organization, show_past_bookings, status, user, hide_recurring_bookings, page_number
):
    organizations = organizations_with_confirmed_bookingpermission(user)
    related_fields = [
        "organization",
        "resource__compensations_of_resource",
        "user",
        "booking_series",
    ]
    bookings = Booking.objects.filter(organization__in=organizations).prefetch_related(
        *related_fields
    )
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if hide_recurring_bookings:
        bookings = bookings.filter(booking_series__isnull=True)

    paginator = Paginator(bookings, 100)
    page_objects = paginator.get_page(page_number)
    bookings = page_objects

    return bookings, organizations


def confirm_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied

    if booking.is_confirmable():
        with set_actor(user):
            booking.status = BookingStatus.CONFIRMED
            booking.save()
            return booking

    raise InvalidBookingOperationError


def manager_filter_bookings_list(  # noqa: PLR0913
    organization,
    show_past_bookings,
    status,
    show_recurring_bookings,
    resource,
    date_string,
):
    organizations = Organization.objects.all()
    resources = Resource.objects.all()
    related_fields = [
        "organization",
        "resource__compensations_of_resource",
        "user",
        "booking_series",
    ]
    bookings = Booking.objects.prefetch_related(*related_fields)
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if resource != "all":
        bookings = bookings.filter(resource__slug=resource)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if not show_recurring_bookings:
        bookings = bookings.filter(booking_series__isnull=True)
    if date_string:
        shown_date = parser.parse(date_string).date()
        start_of_day = timezone.make_aware(
            datetime.combine(shown_date, time(hour=0)),
        )
        end_of_day = timezone.make_aware(
            datetime.combine(shown_date, time(hour=23, minute=59)),
        )
        bookings = bookings.filter(timespan__overlap=(start_of_day, end_of_day))

    bookings = bookings.order_by("timespan")

    return bookings, organizations, resources


def manager_cancel_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if booking.is_cancelable():
        with set_actor(user):
            booking.status = BookingStatus.CANCELLED
            booking.save()
        async_task(
            "re_sharing.organizations.mails.booking_cancellation_email",
            booking,
            task_name="cancel-booking-email",
        )

        return booking

    raise InvalidBookingOperationError


def manager_confirm_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)
    if booking.is_confirmable():
        with set_actor(user):
            booking.status = BookingStatus.CONFIRMED
            booking.save()
        async_task(
            "re_sharing.organizations.mails.booking_confirmation_email",
            booking,
            task_name="booking-confirmation-email",
        )

        return booking

    raise InvalidBookingOperationError


def manager_confirm_booking_series(user, booking_series_uuid):
    booking_series = get_object_or_404(BookingSeries, uuid=booking_series_uuid)
    bookings = get_list_or_404(Booking, booking_series=booking_series)
    booking_series.status = BookingStatus.CONFIRMED
    booking_series.save()
    for booking in bookings:
        if booking.is_confirmable():
            with set_actor(user):
                booking.status = BookingStatus.CONFIRMED
                booking.save()
    async_task(
        "re_sharing.organizations.mails.recurrence_confirmation_email",
        booking_series,
        task_name="recurrence-confirmation-email",
    )

    return booking_series


def collect_booking_reminder_mails():
    bookings = Booking.objects.filter(status=BookingStatus.CONFIRMED)
    dt_in_5_days = timezone.now() + timedelta(days=5)
    dt_in_5_days = dt_in_5_days.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_in_6_days = dt_in_5_days + timedelta(days=1)
    bookings = bookings.filter(timespan__startswith__gte=dt_in_5_days)
    bookings = bookings.filter(timespan__startswith__lt=dt_in_6_days)
    bookings = bookings.filter(
        Q(booking_series__isnull=True) | Q(booking_series__reminder_emails=True)
    )
    processed_slugs = []

    for booking in bookings:
        async_task(
            "re_sharing.organizations.mails.booking_reminder_email",
            booking,
            task_name="booking-reminder-email",
        )
        processed_slugs.append(booking.slug)
    return processed_slugs


def manager_filter_invoice_bookings_list(
    organization, only_with_invoice_number, invoice_number, resource
):
    organizations = Organization.objects.all()
    resources = Resource.objects.all()
    related_fields = [
        "organization",
        "resource__compensations_of_resource",
        "user",
        "booking_series",
    ]

    bookings = (
        Booking.objects.filter(total_amount__gt=0)
        .filter(status=BookingStatus.CONFIRMED)
        .prefetch_related(*related_fields)
    )
    if organization != "all":
        bookings = bookings.filter(organization__slug=organization)
    if invoice_number:
        bookings = bookings.filter(invoice_number=invoice_number)
    if resource != "all":
        bookings = bookings.filter(resource__slug=resource)
    if only_with_invoice_number:
        bookings = bookings.exclude(invoice_number="")

    bookings = bookings.order_by("timespan")

    return bookings, organizations, resources
