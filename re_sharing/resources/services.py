from datetime import datetime
from datetime import time
from datetime import timedelta

from dateutil import parser
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from re_sharing.bookings.models import Booking
from re_sharing.organizations.models import Organization
from re_sharing.resources.models import AccessCode
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Location
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceRestriction
from re_sharing.utils.models import BookingStatus


def show_resource(resource_slug, date_string):
    resource = get_object_or_404(Resource, slug=resource_slug)
    # Calculate the start and end dates for the week
    shown_date = (
        parser.parse(date_string).date() if date_string else timezone.now().date()
    )
    start_of_week = timezone.make_aware(
        datetime.combine(
            shown_date - timedelta(days=shown_date.weekday()), datetime.min.time()
        ),
    )
    end_of_week = timezone.make_aware(
        datetime.combine(start_of_week + timedelta(days=6), datetime.max.time()),
    )
    start_of_day = timezone.make_aware(
        datetime.combine(
            shown_date - timedelta(days=shown_date.weekday()), time(hour=6)
        ),
    )
    # Calculate the time slots for each day
    number_of_slots = 36
    time_slots = [
        {"time": start_of_day + timedelta(minutes=30) * i, "booked": [False] * 7}
        for i in range(number_of_slots)
    ]

    weekdays = [start_of_week + timedelta(days=i) for i in range(7)]

    time_slots = []
    for i in range(number_of_slots):
        slot = {"time": start_of_day + timedelta(minutes=30) * i, "booked": [False] * 7}
        for j in range(7):
            slot["booked"][j] = (
                f"?starttime={slot['time'].strftime('%H:%M')}&endtime="
                f"{(slot['time'] + relativedelta(minutes=90)).strftime('%H:%M')}"
                f"&startdate={weekdays[j].strftime('%Y-%m-%d')}&resource={resource.slug}"
            )
        time_slots.append(slot)

    # Filter bookings for the current week
    weekly_bookings = (
        Booking.objects.filter(resource=resource)
        .filter(status=BookingStatus.CONFIRMED)
        .filter(timespan__overlap=(start_of_week, end_of_week))
        .select_related("resource", "organization")
        .prefetch_related("organization__organization_groups")
    )
    # Check if a time slot is booked
    current_tz = timezone.get_current_timezone()
    if weekly_bookings:
        for booking in weekly_bookings:
            booking_start = max(
                booking.timespan.lower.astimezone(current_tz),
                start_of_week,
            )
            booking_end = min(
                booking.timespan.upper.astimezone(current_tz), end_of_week
            )
            while booking_start < booking_end:
                # Restart the time with start of each day
                start_of_day = booking_start.replace(hour=6, minute=0, second=0)
                if start_of_week <= booking_start < end_of_week:
                    day_index = (booking_start - start_of_week).days
                    slot_index = (booking_start - start_of_day).seconds // (30 * 60)
                    if 0 <= slot_index < number_of_slots:
                        time_slots[slot_index]["booked"][day_index] = True
                booking_start += timedelta(minutes=30)
    dates = {
        "previous_week": shown_date - timedelta(days=7),
        "shown_date": shown_date,
        "next_week": shown_date + timedelta(days=7),
    }
    compensations = Compensation.objects.filter(resource=resource, is_active=True)
    restrictions = ResourceRestriction.objects.filter(resources=resource)
    return resource, time_slots, weekdays, dates, compensations, restrictions


def filter_resources(  # noqa: PLR0913
    user,
    persons_count,
    start_datetime,
    location_slug=None,
    duration=None,
    resource_type=None,
):
    """
    Filters resources based on persons_count, start_datetime, location,
    duration, resource_type, and user's permissions.

    Args:
        persons_count (int): Minimum number of persons the resource must accommodate.
        start_datetime (str): The start datetime to filter resources that are not
        booked.
        user (User): The user for whom the resources are being filtered.
        location_slug (str, optional): Slug of the location to filter by.
        duration (str or int, optional): Duration in minutes for the booking.
        Defaults to 30 minutes.
        resource_type (str, optional): Type of resource to filter by (e.g., 'room',
        'parking_lot'). Defaults to None (all types).

    Returns:
        QuerySet: A filtered queryset of resources, including only the resources the
        user is allowed to see.
    """
    if user.is_authenticated:
        resources = user.get_resources()
    else:
        resources = Resource.objects.filter(is_private=False)

    # Filter resources by type
    if resource_type:
        resources = resources.filter(type=resource_type)

    # Filter resources based on persons_count
    if persons_count:
        resources = resources.filter(max_persons__gte=persons_count)

    # Filter resources by location
    if location_slug:
        resources = resources.filter(location__slug=location_slug)

    # Exclude resources that overlap with other bookings at the specified time
    if start_datetime:
        start_datetime = timezone.make_aware(parser.parse(start_datetime))
        # Use provided duration or default to 30 minutes
        booking_duration = int(duration) if duration else 30
        end_datetime = start_datetime + timedelta(minutes=booking_duration)
        overlapping_bookings = Booking.objects.filter(
            status=BookingStatus.CONFIRMED,
            timespan__overlap=(start_datetime, end_datetime),
        ).select_related("resource", "organization")
        booked_resource_ids = overlapping_bookings.values_list("resource_id", flat=True)
        resources = resources.exclude(id__in=booked_resource_ids)

    # Prefetch related data to optimize performance
    return resources.prefetch_related(
        "resourceimages_of_resource", "compensations_of_resource"
    )


def get_access_code(resource_slug, organization_slug, timestamp):
    resource = get_object_or_404(Resource, slug=resource_slug)
    organization = get_object_or_404(Organization, slug=organization_slug)

    access_code = (
        AccessCode.objects.filter(
            Q(access=resource.access)
            & Q(validity_start__lte=timestamp)
            & Q(organization=organization)
        )
        .order_by("-validity_start")
        .first()
    )

    # when there is no organization specific AccessCode,
    # we try to get the general, unspecific one
    if not access_code:
        access_code = (
            AccessCode.objects.filter(
                Q(access=resource.access)
                & Q(validity_start__lte=timestamp)
                & Q(organization=None)
            )
            .order_by("-validity_start")
            .first()
        )

    return access_code


def _get_timeslot_status(slot_time, resource_restrictions):
    """
    Determine the status of a timeslot based on time and restrictions.

    Args:
        slot_time: The datetime of the slot
        resource_restrictions: List of restrictions for the resource

    Returns:
        tuple: (status, restriction_message)
    """
    # Check if the slot is in the past
    if slot_time <= (timezone.now() - timedelta(minutes=29)):
        return "past", None

    # Default status is bookable
    status = "bookable"
    restriction_message = None

    # Check if any restrictions apply
    for restriction in resource_restrictions:
        if restriction.applies_to_datetime(slot_time):
            status = "restricted"
            restriction_message = restriction.message
            break

    return status, restriction_message


def _create_timeslot(slot_time, status, day, resource_slug, restriction_message=None):
    """
    Create a timeslot data structure.

    Args:
        slot_time: The datetime of the slot
        status: Status of the timeslot (bookable, restricted, past)
        day: The day this timeslot belongs to
        resource_slug: Slug of the resource
        restriction_message: Optional message for restricted slots

    Returns:
        dict: Timeslot data structure
    """
    timeslot = {
        "time": slot_time,
        "status": status,
        "link": None
        if status in {"past", "booked"}
        else (
            f"?starttime={slot_time.strftime('%H:%M')}"
            f"&endtime="
            f"{(slot_time + timedelta(minutes=90)).strftime('%H:%M')}"
            f"&startdate={day.date()}&resource={resource_slug}"
        ),
    }

    if restriction_message and status == "restricted":
        timeslot["restriction_message"] = restriction_message

    return timeslot


def _process_bookings(resource_data, bookings, resource, day, user_context):
    """
    Process bookings for a resource and day, updating timeslot statuses.

    Args:
        resource_data: Resource data structure containing timeslots
        bookings: QuerySet of bookings
        resource: The resource being processed
        day: The day being processed
        user_context: Dictionary containing user and their organizations
    """
    user = user_context.get("user")
    organizations_of_user = user_context.get("organizations", [])
    for booking in bookings:
        if booking.resource != resource or booking.timespan.lower.date() != day.date():
            continue

        booking_start = booking.timespan.lower
        booking_end = booking.timespan.upper

        for timeslot in resource_data["timeslots"]:
            slot_time = timeslot["time"].time()
            slot_datetime = timezone.make_aware(datetime.combine(day.date(), slot_time))

            if booking_start <= slot_datetime < booking_end:
                timeslot["status"] = "booked"
                timeslot["link"] = None

                if booking.organization in organizations_of_user:
                    timeslot["status"] = "booked by me"
                    timeslot["link"] = f"/bookings/{booking.slug}/"
                    timeslot["title"] = booking.title
                    timeslot["organization"] = booking.organization.name

                if user.is_authenticated and booking.organization.is_public:
                    timeslot["organization"] = booking.organization.name
                    timeslot["link"] = f"/organizations/{booking.organization.slug}/"

                if user.is_authenticated and user.is_manager():
                    timeslot["organization"] = booking.organization.name
                    timeslot["link"] = f"/bookings/{booking.slug}/"


def planner(user, date_string, nb_of_days, resources):
    """
    Generate planner data for resources over a specified number of days.
    """
    resources = resources.order_by("access__id", "name")

    shown_date = (
        parser.parse(date_string)
        if date_string
        else timezone.now().replace(hour=0, minute=0, second=0)
    )
    start_of_day = timezone.make_aware(
        datetime.combine(
            shown_date - timedelta(days=shown_date.weekday()), time(hour=6)
        ),
    )
    weekdays = [shown_date + timedelta(days=i) for i in range(nb_of_days)]

    slots_start = 7  # Start at 6 AM
    number_of_slots = 34  # 16 hours (6 AM - 10 PM), 30-minute intervals
    slot_interval_minutes = 30

    # Fetch bookings
    bookings = Booking.objects.filter(
        resource__in=resources,
        status=BookingStatus.CONFIRMED,
        timespan__overlap=(
            shown_date,
            shown_date + timedelta(days=nb_of_days),
        ),
    ).prefetch_related("resource", "organization")

    # Fetch all active restrictions for all resources at once
    all_restrictions = ResourceRestriction.objects.filter(
        is_active=True, resources__in=resources
    ).prefetch_related("resources", "exempt_organization_groups")

    # Create a dictionary to store restrictions by resource
    restrictions_by_resource = {}
    for resource in resources:
        restrictions_by_resource[resource.id] = [
            restriction
            for restriction in all_restrictions
            if resource in restriction.resources.all()
        ]

    # Prepare planner_data
    planner_data = {}
    organizations_of_user = (
        user.get_organizations_of_user() if user.is_authenticated else []
    )

    # Process each day
    for day in weekdays:
        day_data = {"weekday": day, "resources": []}

        # Process each resource
        for resource in resources:
            resource_data = {
                "name": resource.name,
                "timeslots": [],
                "slug": resource.slug,
            }

            # Get start time for this day
            start_time = timezone.make_aware(
                datetime.combine(day, time(hour=slots_start))
            )

            # Get restrictions for this resource
            resource_restrictions = restrictions_by_resource.get(resource.id, [])

            # Create timeslots
            for i in range(number_of_slots):
                slot_time = start_time + timedelta(minutes=slot_interval_minutes * i)

                # Determine status and restriction message
                status, restriction_message = _get_timeslot_status(
                    slot_time, resource_restrictions
                )

                # Create timeslot
                timeslot = _create_timeslot(
                    slot_time, status, day, resource.slug, restriction_message
                )

                resource_data["timeslots"].append(timeslot)

            # Process bookings for this resource and day
            user_context = {
                "user": user,
                "organizations": organizations_of_user,
            }
            _process_bookings(resource_data, bookings, resource, day, user_context)

            day_data["resources"].append(resource_data)

        planner_data[day] = day_data

    # Create timeslots for return value
    timeslots = [
        {"time": start_of_day + timedelta(minutes=30) * i}
        for i in range(number_of_slots)
    ]

    # Create dates for return value
    dates = {
        "previous_day": shown_date - timedelta(days=1),
        "shown_date": shown_date,
        "next_day": shown_date + timedelta(days=1),
    }

    return resources, timeslots, weekdays, dates, planner_data


def get_user_accessible_locations(user):
    """
    Get locations that the user has access to through organization groups.

    A location is accessible if the user is in an organization group that can see
    at least one resource of that location (either bookable_private_resource or
    auto-confirmed_resources).

    Args:
        user (User): The user for whom to get accessible locations.

    Returns:
        QuerySet: A queryset of Location objects that the user has access to.
    """
    if not user.is_authenticated:
        # For unauthenticated users, return locations of public resources
        return (
            Location.objects.filter(resource_of_location__is_private=False)
            .distinct()
            .order_by("name")
        )

    # Get the user's organizations
    user_organizations = user.get_organizations_of_user()

    # Get organization groups of the user's organizations
    org_groups = user_organizations.values_list("organization_groups", flat=True)

    # Get locations of resources that the user can access through organization groups
    # (either bookable_private_resource or auto-confirmed_resources)
    return (
        Location.objects.filter(
            Q(resource_of_location__is_private=False)  # Public resources
            | Q(
                resource_of_location__bookableprivateressource_of_organizationgroup__in=org_groups
            )  # Private resources via org groups
            | Q(
                resource_of_location__autoconfirmedresource_of_organizationgroup__in=org_groups
            )  # Auto-confirmed resources via org groups
        )
        .distinct()
        .order_by("name")
    )
