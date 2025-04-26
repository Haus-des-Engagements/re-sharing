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
from re_sharing.resources.models import Resource
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
    return resource, time_slots, weekdays, dates, compensations


def filter_resources(user, persons_count, start_datetime):
    """
    Filters resources based on persons_count, start_datetime, and user's permissions.

    Args:
        persons_count (int): Minimum number of persons the resource must accommodate.
        start_datetime (str): The start datetime to filter resources that are not
        booked.
        user (User): The user for whom the resources are being filtered.

    Returns:
        QuerySet: A filtered queryset of resources, including only the resources the
        user is allowed to see.
    """
    if user.is_authenticated:
        resources = user.get_resources()
    else:
        resources = Resource.objects.filter(is_private=False)

    # Filter resources based on persons_count
    if persons_count:
        resources = resources.filter(max_persons__gte=persons_count)

    # Exclude resources that overlap with other bookings at the specified time
    if start_datetime:
        start_datetime = timezone.make_aware(parser.parse(start_datetime))
        end_datetime = start_datetime + timedelta(minutes=30)
        overlapping_bookings = Booking.objects.filter(
            timespan__overlap=(start_datetime, end_datetime)
        )
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


def planner(user, date_string, nb_of_days, resources):  # noqa: C901
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

    # Prepare planner_data
    planner_data = {}
    organizations_of_user = (
        user.get_organizations_of_user() if user.is_authenticated else []
    )
    for day in weekdays:
        day_data = {"weekday": day, "resources": []}

        for resource in resources:
            resource_data = {
                "name": resource.name,
                "timeslots": [],
                "slug": resource.slug,
            }
            start_time = timezone.make_aware(
                datetime.combine(day, time(hour=slots_start))
            )
            for i in range(number_of_slots):
                slot_time = start_time + timedelta(minutes=slot_interval_minutes * i)
                if slot_time > (timezone.now() - timedelta(minutes=29)):
                    status = "bookable"
                else:
                    status = "past"
                timeslot = {
                    "time": slot_time,
                    "status": status,
                    "link": (
                        f"?starttime={slot_time.strftime('%H:%M')}"
                        f"&endtime="
                        f"{(slot_time + timedelta(minutes=90)).strftime('%H:%M')}"
                        f"&startdate={day.date()}&resource={resource.slug}"
                    ),
                }
                resource_data["timeslots"].append(timeslot)

            # Check bookings for this resource and day
            for booking in bookings:
                if (
                    booking.resource == resource
                    and booking.timespan.lower.date() == day.date()
                ):
                    booking_start = booking.timespan.lower
                    booking_end = booking.timespan.upper

                    for timeslot in resource_data["timeslots"]:
                        slot_time = timeslot["time"].time()
                        slot_datetime = timezone.make_aware(
                            datetime.combine(day.date(), slot_time)
                        )
                        if booking_start <= slot_datetime < booking_end:
                            timeslot["status"] = "booked"
                            timeslot["link"] = None
                            if booking.organization in organizations_of_user:
                                timeslot["status"] = "booked by me"
                                timeslot["link"] = f"/bookings/{booking.slug}/"
                                timeslot["title"] = booking.title
                            if user.is_staff:
                                timeslot["link"] = f"/bookings/{booking.slug}/"
                            if (
                                user.is_authenticated and booking.organization.is_public
                            ) or user.is_staff:
                                timeslot["organization"] = booking.organization.name
            day_data["resources"].append(resource_data)

        planner_data[day] = day_data
    timeslots = [
        {"time": start_of_day + timedelta(minutes=30) * i}
        for i in range(number_of_slots)
    ]
    dates = {
        "previous_day": shown_date - timedelta(days=1),
        "shown_date": shown_date,
        "next_day": shown_date + timedelta(days=1),
    }
    return resources, timeslots, weekdays, dates, planner_data
