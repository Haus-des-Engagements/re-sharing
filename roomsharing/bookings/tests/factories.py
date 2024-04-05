import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyDateTime
from psycopg.types.range import Range

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingGroup
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.users.tests.factories import OrganizationFactory
from roomsharing.users.tests.factories import UserFactory


class BookingGroupFactory(DjangoModelFactory):
    title = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.title))
    organization = SubFactory(OrganizationFactory)
    user = SubFactory(UserFactory)

    class Meta:
        model = BookingGroup
        django_get_or_create = ["slug"]


class BookingFactory(DjangoModelFactory):
    uuid = uuid.uuid4()
    room = SubFactory(RoomFactory)
    booking_group = SubFactory(BookingGroupFactory)

    @LazyAttribute
    def timespan(self):
        start = FuzzyDateTime(
            start_dt=datetime(2020, 1, 1, tzinfo=UTC),
            force_minute=30,
            force_second=0,
            force_microsecond=0,
        ).fuzz()
        end = start + timedelta(hours=2)  # Adjust as needed
        return Range(start, end, bounds="()")

    class Meta:
        model = Booking
        django_get_or_create = ["uuid"]
