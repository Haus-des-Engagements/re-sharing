from datetime import timedelta

from django.utils import timezone
from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import SubFactory
from factory import post_generation
from factory.django import DjangoModelFactory

from re_sharing.resources.models import Access
from re_sharing.resources.models import AccessCode
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Location
from re_sharing.resources.models import Resource
from re_sharing.resources.models import ResourceRestriction


class AccessFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    name = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.name))
    instructions = Faker("text", max_nb_chars=512)

    class Meta:
        model = Access
        django_get_or_create = ["slug"]


class LocationFactory(DjangoModelFactory):
    name = Faker("word")
    address = Faker("address")

    class Meta:
        model = Location


class ResourceFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    name = Faker("word")
    slug = LazyAttribute(lambda o: slugify(o.name))
    description = Faker("text", max_nb_chars=512)
    square_meters = Faker("random_int", min=1, max=400)
    max_persons = Faker("random_int", min=1, max=100)
    bookable_times = Faker("sentence", nb_words=6)
    included_equipment = Faker("sentence", nb_words=6)
    accessibility = Faker("sentence", nb_words=6)
    access = SubFactory(AccessFactory)
    location = SubFactory(LocationFactory)
    is_private = False

    class Meta:
        model = Resource
        django_get_or_create = ["slug"]


class AccessCodeFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
    access = SubFactory(AccessFactory)
    code = Faker("lexify", text="??????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    validity_start = timezone.now() - timedelta(days=10)
    organization = SubFactory(
        "re_sharing.organizations.tests.factories.OrganizationFactory"
    )

    class Meta:
        model = AccessCode
        django_get_or_create = ["uuid"]


class CompensationFactory(DjangoModelFactory):
    name = Faker("word")
    conditions = Faker("sentence", nb_words=6)
    hourly_rate = Faker("random_int", min=1, max=1000)

    @post_generation
    def resource(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing
            return

        if extracted:
            # A list of resources were passed in, use them
            for resource in extracted:
                self.resource.add(resource)

    class Meta:
        model = Compensation
        skip_postgeneration_save = True


class ResourceRestrictionFactory(DjangoModelFactory):
    start_time = Faker("time_object")
    end_time = Faker("time_object")
    days_of_week = "0,1,2,3,4"  # Monday to Friday
    message = Faker("sentence")
    is_active = True

    @post_generation
    def resources(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing
            return

        if extracted:
            # A list of resources was passed in, use it
            for resource in extracted:
                self.resources.add(resource)

    @post_generation
    def exempt_organization_groups(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing
            return

        if extracted:
            # A list of organization groups was passed in, use it
            for org_group in extracted:
                self.exempt_organization_groups.add(org_group)

    class Meta:
        model = ResourceRestriction
        skip_postgeneration_save = True
