import random
from datetime import datetime
from datetime import time
from datetime import timedelta

from django.utils import timezone
from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory.django import DjangoModelFactory
from psycopg.types.range import Range

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingMessage
from roomsharing.users.tests.factories import UserFactory
from roomsharing.utils.models import BookingStatus


class BookingFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    title = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.title))
    organization = SubFactory(
        "roomsharing.organizations.tests.factories.OrganizationFactory"
    )
    user = SubFactory(UserFactory)
    room = SubFactory("roomsharing.rooms.tests.factories.RoomFactory")
    status = BookingStatus.CONFIRMED
    start_date = Faker(
        "date_between_dates",
        date_start=datetime(2020, 1, 1).date(),  # noqa: DTZ001
        date_end=timezone.now().date() + timedelta(days=300),
    )

    @LazyAttribute
    def start_time(self):
        hour = random.randint(0, 21)  # noqa: S311
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
