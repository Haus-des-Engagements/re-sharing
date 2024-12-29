import random
from datetime import datetime
from datetime import time
from datetime import timedelta

from dateutil.rrule import rrulestr
from django.utils import timezone
from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory.django import DjangoModelFactory
from psycopg.types.range import Range

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingMessage
from re_sharing.bookings.models import RecurrenceRule
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


def create_timespan(start_datetime, duration_in_hours):
    if start_datetime is None:
        start_datetime = timezone.now()
    if duration_in_hours is None:
        duration_in_hours = 2

    return Range(start_datetime, start_datetime + timedelta(hours=duration_in_hours))


class BookingFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    title = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.title))
    organization = SubFactory(
        "re_sharing.organizations.tests.factories.OrganizationFactory"
    )
    user = SubFactory(UserFactory)
    resource = SubFactory("re_sharing.resources.tests.factories.ResourceFactory")
    status = BookingStatus.CONFIRMED
    start_date = Faker(
        "date_between_dates",
        date_start=datetime(2020, 1, 1).date(),  # noqa: DTZ001
        date_end=timezone.now().date() + timedelta(days=300),
    )
    end_date = start_date

    @LazyAttribute
    def start_time(self):
        hour = random.randint(0, 20)  # noqa: S311
        minute = random.choice([0, 30])  # Minute should be either 0 or 30 # noqa: S311
        return time(hour, minute)

    @LazyAttribute
    def end_time(self):
        return (
            datetime.combine(self.start_date, self.start_time)
            + timedelta(minutes=random.choice([30, 60, 90, 120, 150]))  # noqa: S311
        ).time()

    @LazyAttribute
    def timespan(self):
        start_datetime = timezone.make_aware(
            datetime.combine(self.start_date, self.start_time)
        )
        end_datetime = timezone.make_aware(
            datetime.combine(self.start_date, self.end_time)
        )
        return Range(start_datetime, end_datetime)

    class Meta:
        model = Booking
        django_get_or_create = ["slug"]


class BookingMessageFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    text = Faker("word")
    user = SubFactory(UserFactory)
    booking = SubFactory(BookingFactory)

    class Meta:
        model = BookingMessage
        django_get_or_create = ["uuid"]


class RecurrenceRuleFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    rrule = "RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=5;BYDAY=MO,TU"
    reminder_emails = True
    title = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.title))
    organization = SubFactory(
        "re_sharing.organizations.tests.factories.OrganizationFactory"
    )
    user = SubFactory(UserFactory)
    resource = SubFactory("re_sharing.resources.tests.factories.ResourceFactory")
    status = BookingStatus.CONFIRMED

    @LazyAttribute
    def start_time(self):
        hour = random.randint(0, 20)  # noqa: S311
        minute = random.choice([0, 30])  # Minute should be either 0 or 30 # noqa: S311
        return time(hour, minute)

    @LazyAttribute
    def end_time(self):
        return (
            datetime.combine(timezone.now(), self.start_time)
            + timedelta(minutes=random.choice([30, 60, 90, 120, 150]))  # noqa: S311
        ).time()

    @LazyAttribute
    def first_occurrence_date(self):
        return next(iter(rrulestr(self.rrule)))

    @LazyAttribute
    def last_occurrence_date(self):
        return list(rrulestr(self.rrule))[-1]

    class Meta:
        model = RecurrenceRule
        django_get_or_create = ["slug"]
