from datetime import date

from django.test import TestCase

from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.selectors import get_bookable_compensations
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


class TestGetBookableCompensationsOnExemptResource(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.organization.organization_groups.add(
            OrganizationGroupFactory(
                free_bookings_per_year=1, free_bookings_valid_from=date(2027, 1, 1)
            )
        )
        self.resource = ResourceFactory(exempt_from_free_bookings=True)
        self.other_resource = ResourceFactory()
        self.free_compensation = CompensationFactory(
            hourly_rate=None,
            counts_against_free_bookings=True,
            resource=[self.resource, self.other_resource],
        )
        BookingFactory(
            organization=self.organization,
            resource=self.other_resource,
            compensation=self.free_compensation,
            start_date=date(2027, 2, 1),
            uses_free_booking=True,
        )

    def test_flagged_compensation_offered_without_a_remaining_count(self):
        compensations, remaining = get_bookable_compensations(
            self.organization, self.resource, date(2027, 3, 1)
        )

        assert list(compensations) == [self.free_compensation]
        assert remaining is None

    def test_other_resource_hides_the_flagged_compensation(self):
        compensations, remaining = get_bookable_compensations(
            self.organization, self.other_resource, date(2027, 3, 1)
        )

        assert list(compensations) == []
        assert remaining == 0
