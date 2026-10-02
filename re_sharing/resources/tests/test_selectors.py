from django.test import TestCase

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.selectors import get_paid_fallback_compensations
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory


class TestGetPaidFallbackCompensations(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.resource = ResourceFactory()

    def test_returns_active_hourly_compensations_bookable_for_the_resource(self):
        for_resource = CompensationFactory(hourly_rate=15, resource=[self.resource])
        for_all_resources = CompensationFactory(hourly_rate=20)

        result = get_paid_fallback_compensations(self.organization, self.resource)

        assert set(result) == {for_resource, for_all_resources}

    def test_excludes_inactive_and_rate_less_compensations(self):
        CompensationFactory(hourly_rate=15, is_active=False)
        CompensationFactory(hourly_rate=None)

        result = get_paid_fallback_compensations(self.organization, self.resource)

        assert list(result) == []

    def test_excludes_compensations_of_other_resources(self):
        CompensationFactory(hourly_rate=15, resource=[ResourceFactory()])

        result = get_paid_fallback_compensations(self.organization, self.resource)

        assert list(result) == []

    def test_group_restricted_compensations_need_group_membership(self):
        group = OrganizationGroupFactory()
        restricted = CompensationFactory(hourly_rate=15)
        restricted.organization_groups.add(group)

        assert (
            list(get_paid_fallback_compensations(self.organization, self.resource))
            == []
        )

        self.organization.organization_groups.add(group)

        assert list(
            get_paid_fallback_compensations(self.organization, self.resource)
        ) == [restricted]

    def test_compensation_is_listed_once_with_several_matching_groups(self):
        first_group = OrganizationGroupFactory()
        second_group = OrganizationGroupFactory()
        self.organization.organization_groups.add(first_group, second_group)
        compensation = CompensationFactory(hourly_rate=15)
        compensation.organization_groups.add(first_group, second_group)

        result = get_paid_fallback_compensations(self.organization, self.resource)

        assert list(result) == [compensation]
