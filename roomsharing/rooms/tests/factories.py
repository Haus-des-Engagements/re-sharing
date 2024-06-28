from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory.django import DjangoModelFactory

from roomsharing.rooms.models import Room
from roomsharing.users.tests.factories import UserFactory


class RoomFactory(DjangoModelFactory):
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

    class Meta:
        model = Room
        django_get_or_create = ["slug"]
