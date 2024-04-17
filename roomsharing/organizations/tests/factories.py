from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory.django import DjangoModelFactory

from roomsharing.organizations.models import Organization


class OrganizationFactory(DjangoModelFactory):
    name = Faker("company", locale="de_DE")
    slug = LazyAttribute(lambda o: slugify(o.name))
    street = Faker("street_name", locale="de_DE")
    house_number = Faker("building_number", locale="de_DE")
    zip_code = Faker("postcode", locale="de_DE")
    city = Faker("city", locale="de_DE")

    class Meta:
        model = Organization
        django_get_or_create = ["slug"]
