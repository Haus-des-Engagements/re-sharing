from datetime import datetime
from datetime import time
from datetime import timedelta
from http import HTTPStatus

from auditlog.context import set_actor
from dateutil import parser
from dateutil.parser import isoparse
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_list_or_404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingMessage
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.services_booking_series import create_rrule
from re_sharing.organizations.mails import send_booking_cancellation_email
from re_sharing.organizations.mails import send_booking_confirmation_email
from re_sharing.organizations.mails import send_booking_not_available_email
from re_sharing.organizations.mails import send_booking_series_confirmation_email
from re_sharing.organizations.mails import send_manager_new_booking_email
from re_sharing.organizations.mails import send_new_booking_message_email
from re_sharing.organizations.models import Organization
from re_sharing.organizations.services import (
    organizations_with_confirmed_bookingpermission,
)
from re_sharing.organizations.services import user_has_bookingpermission
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Location
from re_sharing.resources.models import Resource
from re_sharing.resources.services import get_access_code
from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus
from re_sharing.utils.models import get_booking_status


class InvalidBookingOperationError(Exception):
    def __init__(self):
        self.message = "You cannot perform this action."
        self.status_code = HTTPStatus.BAD_REQUEST


def is_bookable_by_organization(user, organization, resource, compensation):
    # staff users are allowed to book any combination
    if user.is_manager():
        return True

    # check if organization is confirmed
    if organization.status != Organization.Status.CONFIRMED:
        return False

    # check if user is allowed to book for that organization
    if not organization.has_confirmed_user(user):
        return False

    # check if resource and compensations are bookable
    if resource.is_bookable_by_organization(
        organization
    ) and compensation.is_bookable_by_organization(organization):
        return True

    return False


def set_initial_booking_data(**kwargs):
    endtime = kwargs.get("endtime")
    startdate = kwargs.get("startdate")
    starttime = kwargs.get("starttime")
    resource = kwargs.get("resource")
    organization = kwargs.get("organization")
    title = kwargs.get("title")
    activity_description = kwargs.get("activity_description")
    attendees = kwargs.get("attendees")
    import_id = kwargs.get("import_id")

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
    if organization:
        initial_data["organization"] = get_object_or_404(
            Organization, slug=organization
        )
    if title:
        initial_data["title"] = title
    if activity_description:
        initial_data["activity_description"] = activity_description
    if attendees:
        initial_data["number_of_attendees"] = attendees
    if import_id:
        initial_data["import_id"] = import_id

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
        "number_of_attendees": form.cleaned_data["number_of_attendees"],
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
    user = get_object_or_404(User, slug=booking_data["user"])

    start = timespan[0]
    end = timespan[1]
    compensation = get_object_or_404(Compensation, id=booking_data["compensation"])
    if compensation.hourly_rate is not None:
        total_amount = (end - start).total_seconds() / 3600 * compensation.hourly_rate
    else:
        total_amount = None

    if booking_data.get("booking_id"):
        # Retrieve the existing booking object
        booking = get_object_or_404(Booking, id=booking_data["booking_id"])
        if booking.total_amount != total_amount:
            booking.total_amount = total_amount

        # Update the existing object's fields
        booking.user = user
        booking.title = booking_data["title"]
        booking.number_of_attendees = booking_data["number_of_attendees"]
        booking.resource = resource
        booking.organization = organization
        booking.status = get_booking_status(user, organization, resource)
        booking.timespan = timespan
        booking.start_date = booking_data["start_date"]
        booking.end_date = booking_data["end_date"]
        booking.start_time = booking_data["start_time"]
        booking.end_time = booking_data["end_time"]
        booking.compensation = compensation
        booking.invoice_address = booking_data["invoice_address"]
        booking.activity_description = booking_data["activity_description"]

    else:
        # Create a new booking object
        booking = Booking(
            user=user,
            title=booking_data["title"],
            number_of_attendees=booking_data.get("number_of_attendees", 5),
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
        )

    return booking


def save_booking(user, booking):
    if not user_has_bookingpermission(user, booking):
        raise PermissionDenied
    if not is_bookable_by_organization(
        user, booking.organization, booking.resource, booking.compensation
    ):
        raise PermissionDenied

    booking.save()
    # re-retrieve booking object, to be able to call timespan.lower
    booking.refresh_from_db()
    if booking.status == BookingStatus.PENDING:
        send_manager_new_booking_email(booking)

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
        if booking.timespan.lower > (timezone.now() + timedelta(days=7)):
            access_code = _("only shown 7 days before booking")
        else:
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
    send_new_booking_message_email(booking_message)

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


def process_field_changes(field, values):  # noqa: C901, PLR0912, PLR0915
    """Process specific field changes and return formatted details."""
    old_value, new_value = values

    # Generic structure for change details:
    change_details = {
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
    }

    # Handle field-specific cases
    if field == "user":
        try:
            old_user = User.objects.get(id=int(old_value))
            old_user_display = f"{old_user.first_name} {old_user.last_name}"
        except User.DoesNotExist:
            old_user_display = _("(deleted)")

        try:
            new_user = User.objects.get(id=int(new_value))
            new_user_display = f"{new_user.first_name} {new_user.last_name}"
        except User.DoesNotExist:
            new_user_display = _("(deleted)")

        change_details.update(
            {
                "field": _("User"),
                "old_value": old_user_display,
                "new_value": new_user_display,
            }
        )
    elif field == "start_date":
        change_details.update(
            {
                "field": _("Start Date"),
                "old_value": datetime.strptime(old_value, "%Y-%m-%d").strftime(  # noqa: DTZ007
                    "%d.%m.%Y"
                ),
                "new_value": datetime.strptime(new_value, "%Y-%m-%d").strftime(  # noqa: DTZ007
                    "%d.%m.%Y"
                ),
            }
        )
    elif field == "resource":
        try:
            old_resource = Resource.objects.get(id=int(old_value))
            old_resource_display = old_resource.name
        except Resource.DoesNotExist:
            old_resource_display = _("(deleted)")

        try:
            new_resource = Resource.objects.get(id=int(new_value))
            new_resource_display = new_resource.name
        except Resource.DoesNotExist:
            new_resource_display = _("(deleted)")

        change_details.update(
            {
                "field": _("Resource"),
                "old_value": old_resource_display,
                "new_value": new_resource_display,
            }
        )
    elif field == "compensation":
        try:
            old_compensation = Compensation.objects.get(id=int(old_value))
            old_compensation_display = old_compensation.name
        except Compensation.DoesNotExist:
            old_compensation_display = _("(deleted)")

        try:
            new_compensation = Compensation.objects.get(id=int(new_value))
            new_compensation_display = new_compensation.name
        except Compensation.DoesNotExist:
            new_compensation_display = _("(deleted)")

        change_details.update(
            {
                "field": _("Compensation"),
                "old_value": old_compensation_display,
                "new_value": new_compensation_display,
            }
        )
    elif field == "organization":
        try:
            old_organization = Organization.objects.get(id=int(old_value))
            old_organization_display = old_organization.name
        except Organization.DoesNotExist:
            old_organization_display = _("(deleted)")

        try:
            new_organization = Organization.objects.get(id=int(new_value))
            new_organization_display = new_organization.name
        except Organization.DoesNotExist:
            new_organization_display = _("(deleted)")

        change_details.update(
            {
                "field": _("Organization"),
                "old_value": old_organization_display,
                "new_value": new_organization_display,
            }
        )
    elif field == "status":
        old_value_text = dict(BookingStatus.choices).get(int(old_value))
        new_value_text = dict(BookingStatus.choices).get(int(new_value))
        change_details.update(
            {
                "field": _("Status"),
                "old_value": old_value_text,
                "new_value": new_value_text,
            }
        )
    elif field in ("start_time", "end_time"):
        change_details.update(
            {
                "field": _(field.replace("_", " ").capitalize()),
                "old_value": datetime.strptime(old_value, "%H:%M:%S").strftime("%H:%M"),  # noqa: DTZ007
                "new_value": datetime.strptime(new_value, "%H:%M:%S").strftime("%H:%M"),  # noqa: DTZ007
            }
        )
    else:
        change_details.update(
            {
                "field": _(field.replace("_", " ").capitalize()),
                "old_value": old_value,
                "new_value": new_value,
            }
        )

    return change_details


def get_booking_activity_stream(booking):
    activity_stream = []
    booking_logs = booking.history.filter(action=1)
    for log_entry in booking_logs:
        changes = log_entry.changes  # Access all changes
        change_details = []

        for field, values in changes.items():
            if field in {"end_date", "timespan"}:
                continue
            processed_change = process_field_changes(field, values)
            change_details.append(processed_change)

        # Get actor, handling deleted users
        try:
            actor = User.objects.get(id=log_entry.actor_id)
        except User.DoesNotExist:
            actor = None

        # Append information for this log entry to the activity stream
        activity_stream.append(
            {
                "date": log_entry.timestamp,
                "type": "change",
                "user": actor,
                "changes": change_details,
            }
        )

    # Retrieve associated booking messages
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


def bookings_webview(location="all"):
    bookings = Booking.objects.filter(
        resource__type=Resource.ResourceTypeChoices.ROOM, status=BookingStatus.CONFIRMED
    )

    # Filter by location if not "all"
    if location != "all":
        location = get_object_or_404(Location, slug=location)
        bookings = bookings.filter(resource__location=location)

    bookings = bookings.filter(
        timespan__overlap=(
            timezone.now(),
            datetime.combine(timezone.now(), time(hour=23, minute=59)),
        )
    )

    bookings = bookings.order_by("timespan")

    return bookings, location


def manager_filter_bookings_list(  # noqa: PLR0913
    organization_search,
    show_past_bookings,
    status,
    show_recurring_bookings,
    resource,
    location,
    from_date_string,
    until_date_string,
    user,
):
    manager = user.get_manager()
    organizations = manager.get_organizations()
    resources = manager.get_resources()

    # Get distinct locations from resources the manager has access to
    locations = (
        Location.objects.filter(resource_of_location__in=resources)
        .distinct()
        .order_by("name")
    )

    related_fields = [
        "organization",
        "resource__compensations_of_resource",
        "resource__location",
        "user",
        "booking_series",
    ]
    bookings = (
        Booking.objects.filter(organization__in=organizations)
        .filter(resource__in=resources)
        .prefetch_related(*related_fields)
    )
    if not show_past_bookings:
        bookings = bookings.filter(timespan__endswith__gte=timezone.now())
    if organization_search:
        bookings = bookings.filter(organization__name__icontains=organization_search)
    if resource != "all":
        bookings = bookings.filter(resource__slug=resource)
    if location != "all":
        bookings = bookings.filter(resource__location__slug=location)
    if status != "all":
        bookings = bookings.filter(status__in=status)
    if not show_recurring_bookings:
        bookings = bookings.exclude(booking_series__isnull=False)

    # Date range filtering
    if from_date_string:
        from_date = parser.parse(from_date_string).date()
        start_of_from_date = timezone.make_aware(
            datetime.combine(from_date, time(hour=0)),
        )
        bookings = bookings.filter(timespan__endswith__gte=start_of_from_date)

    if until_date_string:
        until_date = parser.parse(until_date_string).date()
        end_of_until_date = timezone.make_aware(
            datetime.combine(until_date, time(hour=23, minute=59)),
        )
        bookings = bookings.filter(timespan__startswith__lte=end_of_until_date)

    bookings = bookings.order_by("created")

    return bookings, resources, locations


def manager_cancel_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)

    if booking.is_cancelable():
        with set_actor(user):
            booking.status = BookingStatus.CANCELLED
            booking.save()
        send_booking_cancellation_email(booking)

        return booking

    raise InvalidBookingOperationError


def manager_confirm_booking(user, booking_slug):
    booking = get_object_or_404(Booking, slug=booking_slug)
    if booking.is_confirmable():
        # Check for overlaps with existing confirmed bookings
        overlapping_bookings = Booking.objects.filter(
            status=BookingStatus.CONFIRMED,
            resource=booking.resource,
            timespan__overlap=booking.timespan,
        ).exclude(id=booking.id)

        if overlapping_bookings.exists():
            # Set status to UNAVAILABLE instead of CONFIRMED
            with set_actor(user):
                booking.status = BookingStatus.UNAVAILABLE
                booking.save()
            send_booking_not_available_email(booking)
        else:
            # No overlap, confirm the booking
            with set_actor(user):
                booking.status = BookingStatus.CONFIRMED
                booking.save()
            send_booking_confirmation_email(booking)

        return booking

    raise InvalidBookingOperationError


def manager_confirm_booking_series(user, booking_series_uuid):
    booking_series = get_object_or_404(BookingSeries, uuid=booking_series_uuid)
    bookings = get_list_or_404(Booking, booking_series=booking_series)
    booking_series.status = BookingStatus.CONFIRMED
    booking_series.save()
    for booking in bookings:
        if booking.status != BookingStatus.CANCELLED:
            overlapping_bookings = Booking.objects.filter(
                status=BookingStatus.CONFIRMED,
                resource=booking.resource,
                timespan__overlap=booking.timespan,
            ).exclude(id=booking.id)
            with set_actor(user):
                if overlapping_bookings.exists():
                    booking.status = BookingStatus.UNAVAILABLE
                else:
                    booking.status = BookingStatus.CONFIRMED
                booking.save()

    send_booking_series_confirmation_email(booking_series)
    return booking_series


def manager_filter_invoice_bookings_list(
    organization_search, invoice_filter, invoice_number, resource
):
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
    if organization_search:
        bookings = bookings.filter(organization__name__icontains=organization_search)
    if invoice_number:
        bookings = bookings.filter(invoice_number__icontains=invoice_number)
    if resource != "all":
        bookings = bookings.filter(resource__slug=resource)
    if invoice_filter == "with_invoice":
        bookings = bookings.exclude(invoice_number="")
    elif invoice_filter == "without_invoice":
        bookings = bookings.filter(invoice_number="")

    bookings = bookings.order_by("timespan")

    return bookings, resources


def get_external_events(ics_url: str, cache_key: str = "external_events") -> list[dict]:
    """
    Fetch and parse events from an external ICS calendar feed.

    Returns a list of upcoming events sorted by start date.
    Results are cached for 24 hours.
    """
    import logging

    import requests
    from django.core.cache import cache
    from icalendar import Calendar

    logger = logging.getLogger(__name__)

    # Try cache first
    cached_events = cache.get(cache_key)
    if cached_events is not None:
        return cached_events

    events = []
    try:
        response = requests.get(ics_url, timeout=10)
        response.raise_for_status()

        cal = Calendar.from_ical(response.content)
        today = timezone.now().date()

        for component in cal.walk():
            if component.name == "VEVENT":
                dtstart = component.get("dtstart")
                if dtstart is None:
                    continue

                # Get start date (handle both date and datetime)
                start_dt = dtstart.dt
                start_date = start_dt.date() if hasattr(start_dt, "date") else start_dt

                # Skip past events
                if start_date < today:
                    continue

                # Get end date/time
                dtend = component.get("dtend")
                end_dt = dtend.dt if dtend else None

                events.append(
                    {
                        "title": str(component.get("summary", "")),
                        "start": start_dt,
                        "end": end_dt,
                        "location": str(component.get("location", "")),
                        "description": str(component.get("description", "")),
                        "url": str(component.get("url", "")),
                    }
                )

        # Sort by start date
        events.sort(key=lambda x: x["start"])

    except requests.RequestException:
        logger.exception("Failed to fetch external events from %s", ics_url)
    except Exception:
        logger.exception("Failed to parse ICS feed from %s", ics_url)

    # Cache for 24 hours
    cache.set(cache_key, events, 60 * 60 * 24)
    return events
