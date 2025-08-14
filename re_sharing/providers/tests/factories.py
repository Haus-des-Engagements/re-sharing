from factory import SubFactory
from factory import post_generation
from factory.django import DjangoModelFactory

from re_sharing.providers.models import Manager
from re_sharing.users.tests.factories import UserFactory


class ManagerFactory(DjangoModelFactory):
    user = SubFactory(UserFactory)

    @post_generation
    def resources(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing
            return

        if extracted:
            # A list of resources were passed in, use them
            for resource in extracted:
                self.resources.add(resource)

    @post_generation
    def organization_groups(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing
            return

        if extracted:
            # A list of organization groups were passed in, use them
            for org_group in extracted:
                self.organization_groups.add(org_group)

    class Meta:
        model = Manager
        django_get_or_create = ["user"]
