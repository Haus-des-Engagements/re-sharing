from datetime import timedelta

import pytest
from django.utils import timezone

from re_sharing.bookings.forms import BookingForm
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import BookingPermissionFactory


@pytest.fixture()
def booking_db(resource):
    start_datetime = timezone.now() + timedelta(days=1)
    end_datetime = start_datetime + timedelta(hours=1)
    return BookingFactory(
        resource=resource, timespan=(start_datetime, end_datetime), status=2
    )


@pytest.mark.django_db()
@pytest.mark.parametrize(
    (
        "startdate",
        "starttime",
        "endtime",
        "rrule_repetitions",
        "rrule_ends",
        "rrule_ends_count",
        "rrule_ends_enddate",
        "expected_errors",
    ),
    [
        (
            timezone.now().date() + timedelta(days=1),
            "11:00",
            "09:00",
            "NO_REPETITIONS",
            "NEVER",
            None,
            None,
            ["endtime", "starttime"],
        ),
        (
            timezone.now().date() - timedelta(days=1),
            "09:00",
            "11:00",
            "NO_REPETITIONS",
            "NEVER",
            None,
            None,
            ["startdate", "endtime"],
        ),
        (
            timezone.now().date(),
            "09:00",
            "11:00",
            "DAILY",
            "AFTER_TIMES",
            None,
            None,
            ["rrule_ends_count"],
        ),
        (
            timezone.now().date(),
            "09:00",
            "11:00",
            "DAILY",
            "AT_DATE",
            None,
            timezone.now().date() - timedelta(days=1),
            ["rrule_ends_enddate"],
        ),
        (
            timezone.now().date() + timedelta(days=731),
            "09:00",
            "11:00",
            "NO_REPETITIONS",
            "NEVER",
            None,
            None,
            ["startdate"],
        ),
    ],
)
def test_clean_method(  # noqa: PLR0913
    startdate,
    starttime,
    endtime,
    rrule_repetitions,
    rrule_ends,
    rrule_ends_count,
    rrule_ends_enddate,
    expected_errors,
    user,
    resource,
    organization,
    booking_db,
    compensation,
):
    BookingPermissionFactory(organization=organization, user=user, status=2)
    form_data = {
        "startdate": startdate,
        "starttime": starttime,
        "endtime": endtime,
        "rrule_repetitions": rrule_repetitions,
        "rrule_ends": rrule_ends,
        "rrule_ends_count": rrule_ends_count,
        "rrule_ends_enddate": rrule_ends_enddate,
        "title": "Test title",
        "organization": organization.id,
        "resource": resource.id,
        "number_of_attendees": 20,
        "message": "Test message",
        "compensation": compensation.id,
        "activity_description": "Test activity description",
    }
    form = BookingForm(user=user, data=form_data)

    assert not form.is_valid()
    for field in expected_errors:
        assert field in form.errors


@pytest.fixture()
def series_form_setup(user):
    from datetime import date

    from re_sharing.organizations.models import Organization
    from re_sharing.organizations.tests.factories import OrganizationFactory
    from re_sharing.organizations.tests.factories import OrganizationGroupFactory
    from re_sharing.resources.tests.factories import CompensationFactory
    from re_sharing.resources.tests.factories import ResourceFactory

    organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
    group = OrganizationGroupFactory(
        free_bookings_per_year=2, free_bookings_valid_from=date(2027, 1, 1)
    )
    organization.organization_groups.add(group)
    BookingPermissionFactory(organization=organization, user=user, status=2)
    resource = ResourceFactory()
    free_compensation = CompensationFactory(
        hourly_rate=None, counts_against_free_bookings=True, resource=[resource]
    )
    paid_compensation = CompensationFactory(hourly_rate=15, resource=[resource])
    return {
        "user": user,
        "organization": organization,
        "group": group,
        "resource": resource,
        "free_compensation": free_compensation,
        "paid_compensation": paid_compensation,
    }


def series_form_data(setup, **overrides):
    data = {
        "startdate": timezone.now().date() + timedelta(days=7),
        "starttime": "10:00",
        "endtime": "12:00",
        "rrule_repetitions": "WEEKLY",
        "rrule_ends": "NEVER",
        "rrule_weekly_interval": 1,
        "rrule_weekly_byday": ["MO"],
        "rrule_daily_interval": 1,
        "rrule_monthly_interval": 1,
        "title": "Weekly meeting",
        "organization": setup["organization"].id,
        "resource": setup["resource"].id,
        "number_of_attendees": 5,
        "compensation": setup["free_compensation"].id,
        "activity_description": "Meeting",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db()
def test_fallback_required_for_limited_organization(series_form_setup):
    form = BookingForm(
        user=series_form_setup["user"], data=series_form_data(series_form_setup)
    )

    assert not form.is_valid()
    assert "fallback_compensation" in form.errors


@pytest.mark.django_db()
def test_fallback_accepted_for_limited_organization(series_form_setup):
    form = BookingForm(
        user=series_form_setup["user"],
        data=series_form_data(
            series_form_setup,
            fallback_compensation=series_form_setup["paid_compensation"].id,
        ),
    )

    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["fallback_compensation"]
        == series_form_setup["paid_compensation"]
    )


@pytest.mark.django_db()
def test_fallback_required_for_open_ended_series_starting_before_valid_from(
    series_form_setup,
):
    # today is before 2027-01-01 in this scenario; the horizon reaches into 2027
    form = BookingForm(
        user=series_form_setup["user"],
        data=series_form_data(series_form_setup, rrule_ends="NEVER"),
    )

    assert not form.is_valid()
    assert "fallback_compensation" in form.errors


@pytest.mark.django_db()
def test_fallback_not_required_for_series_ending_before_valid_from(series_form_setup):
    series_form_setup["group"].free_bookings_valid_from = (
        timezone.now().date() + timedelta(days=60)
    )
    series_form_setup["group"].save()
    form = BookingForm(
        user=series_form_setup["user"],
        data=series_form_data(
            series_form_setup,
            rrule_ends="AT_DATE",
            rrule_ends_enddate=timezone.now().date() + timedelta(days=30),
        ),
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["fallback_compensation"] is None


@pytest.mark.django_db()
def test_fallback_not_required_for_series_ending_after_count_before_valid_from(
    series_form_setup,
):
    series_form_setup["group"].free_bookings_valid_from = (
        timezone.now().date() + timedelta(days=60)
    )
    series_form_setup["group"].save()
    form = BookingForm(
        user=series_form_setup["user"],
        data=series_form_data(
            series_form_setup, rrule_ends="AFTER_TIMES", rrule_ends_count=2
        ),
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db()
def test_fallback_not_required_for_unlimited_organization(series_form_setup):
    from re_sharing.organizations.tests.factories import OrganizationGroupFactory

    series_form_setup["organization"].organization_groups.add(
        OrganizationGroupFactory()
    )
    form = BookingForm(
        user=series_form_setup["user"], data=series_form_data(series_form_setup)
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db()
def test_fallback_not_required_without_paid_option(series_form_setup):
    series_form_setup["paid_compensation"].is_active = False
    series_form_setup["paid_compensation"].save()
    form = BookingForm(
        user=series_form_setup["user"], data=series_form_data(series_form_setup)
    )

    assert form.is_valid(), form.errors


@pytest.mark.django_db()
def test_fallback_not_required_for_single_booking(series_form_setup):
    form = BookingForm(
        user=series_form_setup["user"],
        data=series_form_data(
            series_form_setup, rrule_repetitions="NO_REPETITIONS", rrule_weekly_byday=[]
        ),
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["fallback_compensation"] is None


@pytest.mark.django_db()
def test_fallback_must_be_bookable_for_the_resource(series_form_setup):
    from re_sharing.resources.tests.factories import CompensationFactory
    from re_sharing.resources.tests.factories import ResourceFactory

    other = CompensationFactory(hourly_rate=20, resource=[ResourceFactory()])
    form = BookingForm(
        user=series_form_setup["user"],
        data=series_form_data(series_form_setup, fallback_compensation=other.id),
    )

    assert not form.is_valid()
    assert "fallback_compensation" in form.errors
