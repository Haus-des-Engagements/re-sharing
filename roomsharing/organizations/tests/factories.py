from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory.django import DjangoModelFactory

from roomsharing.organizations.models import Membership
from roomsharing.organizations.models import Organization
from roomsharing.users.tests.factories import UserFactory


class OrganizationFactory(DjangoModelFactory):
    name = Faker("company", locale="de_DE")
    slug = LazyAttribute(lambda o: slugify(o.name))
    street = Faker("street_name", locale="de_DE")
    house_number = Faker("building_number", locale="de_DE")
    zip_code = Faker("postcode", locale="de_DE")
    city = Faker("city", locale="de_DE")
    legal_form = 1

    class Meta:
        model = Organization
        django_get_or_create = ["slug"]


class MembershipFactory(DjangoModelFactory):
    organization = SubFactory(OrganizationFactory)
    user = SubFactory(UserFactory)
    role = Membership.Role.BOOKER
    status = Membership.Status.CONFIRMED

    class Meta:
        model = Membership
