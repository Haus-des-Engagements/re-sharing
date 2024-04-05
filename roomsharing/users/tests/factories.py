from collections.abc import Sequence
from typing import Any

from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import post_generation
from factory.django import DjangoModelFactory

from roomsharing.users.models import Organization
from roomsharing.users.models import User


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


class UserFactory(DjangoModelFactory):
    email = Faker("email")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    is_staff = False

    @post_generation
    def password(self, create: bool, extracted: Sequence[Any], **kwargs):  # noqa: FBT001
        password = (
            extracted
            if extracted
            else Faker(
                "password",
                length=42,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ).evaluate(None, None, extra={"locale": None})
        )
        self.set_password(password)

    @classmethod
    def _after_postgeneration(cls, instance, create, results=None):
        """Save again the instance if creating and at least one hook ran."""
        if create and results and not cls._meta.skip_postgeneration_save:
            # Some post-generation hooks ran, and may have modified us.
            instance.save()

    class Meta:
        model = User
        django_get_or_create = ["email"]
