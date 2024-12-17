from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory import post_generation
from factory.django import DjangoModelFactory

from roomsharing.organizations.models import BookingPermission
from roomsharing.organizations.models import Organization
from roomsharing.organizations.models import OrganizationGroup
from roomsharing.users.tests.factories import UserFactory


class OrganizationFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    name = Faker("company", locale="de_DE")
    description = Faker("text", max_nb_chars=512)
    slug = LazyAttribute(lambda o: slugify(o.name))
    street_and_housenb = Faker("street_address", locale="de_DE")
    zip_code = Faker("postcode", locale="de_DE")
    city = Faker("city", locale="de_DE")
    email = Faker("email")
    phone = Faker("phone_number")
    website = Faker("url")
    legal_form = 1
    area_of_activity = Organization.ActivityArea.ENVIRONMENT_NATURE_ANIMALS
    entitled = True
    values_approval = True

    class Meta:
        model = Organization
        django_get_or_create = ["slug"]


class BookingPermissionFactory(DjangoModelFactory):
    organization = SubFactory(OrganizationFactory)
    user = SubFactory(UserFactory)
    role = BookingPermission.Role.BOOKER
    status = BookingPermission.Status.CONFIRMED

    class Meta:
        model = BookingPermission


class OrganizationGroupFactory(DjangoModelFactory):
    name = Faker("company", locale="de_DE")
    description = Faker("text", max_nb_chars=512)
    slug = LazyAttribute(lambda o: slugify(o.name))

    @post_generation
    def auto_confirmed_rooms(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing
            return

        if extracted:
            # A list of rooms were passed in, use them
            for room in extracted:
                self.auto_confirmed_rooms.add(room)

    class Meta:
        model = OrganizationGroup
        skip_postgeneration_save = True
