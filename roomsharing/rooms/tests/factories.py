from datetime import timedelta

from django.utils import timezone
from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory.django import DjangoModelFactory

from roomsharing.rooms.models import Access
from roomsharing.rooms.models import AccessCode
from roomsharing.rooms.models import Room
from roomsharing.users.tests.factories import UserFactory


class AccessFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    name = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.name))
    instructions = Faker("text", max_nb_chars=512)

    class Meta:
        model = Access
        django_get_or_create = ["slug"]


class RoomFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    name = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.name))
    description = Faker("text", max_nb_chars=512)
    square_meters = Faker("random_int", min=1, max=400)
    max_persons = Faker("random_int", min=1, max=100)
    bookable_times = Faker("sentence", nb_words=6)
    pricing = Faker("sentence", nb_words=6)
    included_equipment = Faker("sentence", nb_words=6)
    bookable_equipment = Faker("sentence", nb_words=6)
    manager = SubFactory(UserFactory)
    access = SubFactory(AccessFactory)

    class Meta:
        model = Room
        django_get_or_create = ["slug"]


class AccessCodeFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    access = SubFactory(AccessFactory)
    code = Faker("random_letters", length=6)
    validity_start = Faker(
        "date_between_dates",
        date_start=(timezone.now() - timedelta(days=500)),
        date_end=timezone.now() + timedelta(days=500),
    )
    organization = SubFactory(
        "roomsharing.organizations.tests.factories.OrganizationFactory"
    )

    class Meta:
        model = AccessCode
        django_get_or_create = ["uuid"]
