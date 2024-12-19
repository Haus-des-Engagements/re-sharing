from collections.abc import Sequence
from typing import Any

from django.utils.text import slugify
from factory import Faker
from factory import LazyAttribute
from factory import post_generation
from factory.django import DjangoModelFactory

from roomsharing.users.models import User
from roomsharing.users.models import UserGroup


class UserFactory(DjangoModelFactory):
    uuid = Faker("uuid4")
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


class UserGroupFactory(DjangoModelFactory):
    name = Faker("company", locale="de_DE")
    description = Faker("text", max_nb_chars=512)
    slug = LazyAttribute(lambda o: slugify(o.name))

    class Meta:
        model = UserGroup
        django_get_or_create = ["slug"]
