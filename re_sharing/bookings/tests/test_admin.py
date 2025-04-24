from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.utils import timezone

from re_sharing.bookings.admin import BookingAdmin
from re_sharing.bookings.admin import BookingSeriesAdmin
from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.tests.factories import UserFactory
from re_sharing.utils.models import BookingStatus


class MockRequest:
    def __init__(self, user=None):
        self.user = user


@pytest.fixture()
def booking_admin_setup():
    site = AdminSite()
    admin = BookingAdmin(Booking, site)
    user = UserFactory(is_staff=True)
    request = MockRequest(user=user)
    organization = OrganizationFactory()
    resource = ResourceFactory()

    return {
        "site": site,
        "admin": admin,
        "user": user,
        "request": request,
        "organization": organization,
        "resource": resource,
    }


@pytest.mark.django_db()
def test_confirm_bookings(booking_admin_setup):
    # Create some bookings with PENDING status
    booking1 = BookingFactory(status=BookingStatus.PENDING)
    booking2 = BookingFactory(status=BookingStatus.PENDING)

    # Mock the queryset
    queryset = Booking.objects.filter(id__in=[booking1.id, booking2.id])

    # Mock the message_user method
    booking_admin_setup["admin"].message_user = MagicMock()

    # Call the confirm_bookings action
    booking_admin_setup["admin"].confirm_bookings(
        booking_admin_setup["request"], queryset
    )

    # Refresh the bookings from the database
    booking1.refresh_from_db()
    booking2.refresh_from_db()

    # Check that the bookings were confirmed
    assert booking1.status == BookingStatus.CONFIRMED
    assert booking2.status == BookingStatus.CONFIRMED

    # Check that the message_user method was called
    booking_admin_setup["admin"].message_user.assert_called_once()


@pytest.mark.django_db()
def test_cancel_bookings(booking_admin_setup):
    # Create some bookings with CONFIRMED status
    booking1 = BookingFactory(status=BookingStatus.CONFIRMED)
    booking2 = BookingFactory(status=BookingStatus.CONFIRMED)

    # Mock the queryset
    queryset = Booking.objects.filter(id__in=[booking1.id, booking2.id])

    # Mock the message_user method
    booking_admin_setup["admin"].message_user = MagicMock()

    # Call the cancel_bookings action
    booking_admin_setup["admin"].cancel_bookings(
        booking_admin_setup["request"], queryset
    )

    # Refresh the bookings from the database
    booking1.refresh_from_db()
    booking2.refresh_from_db()

    # Check that the bookings were cancelled
    assert booking1.status == BookingStatus.CANCELLED
    assert booking2.status == BookingStatus.CANCELLED

    # Check that the message_user method was called
    booking_admin_setup["admin"].message_user.assert_called_once()


@pytest.fixture()
def booking_series_admin_setup():
    site = AdminSite()
    admin = BookingSeriesAdmin(BookingSeries, site)
    user = UserFactory(is_staff=True)
    request = MockRequest(user=user)
    organization = OrganizationFactory()
    resource = ResourceFactory()

    return {
        "site": site,
        "admin": admin,
        "user": user,
        "request": request,
        "organization": organization,
        "resource": resource,
    }


@pytest.mark.django_db()
def test_booking_count_link(booking_series_admin_setup):
    # Create a booking series with some bookings
    booking_series = BookingSeriesFactory()
    BookingFactory(booking_series=booking_series)
    BookingFactory(booking_series=booking_series)

    # Manually add the booking_count attribute that would normally
    # be added by get_queryset
    booking_series.booking_count = Booking.objects.filter(
        booking_series=booking_series
    ).count()

    # Mock the reverse function
    with patch("re_sharing.bookings.admin.reverse") as mock_reverse:
        mock_reverse.return_value = "/admin/bookings/booking/"

        # Call the booking_count_link method
        result = booking_series_admin_setup["admin"].booking_count_link(booking_series)

        # Check that the reverse function was called with the correct arguments
        mock_reverse.assert_called_once_with("admin:bookings_booking_changelist")

        # Check that the result contains the correct URL and count
        assert "/admin/bookings/booking/" in result
        assert "2" in result  # 2 bookings


@pytest.mark.django_db()
def test_save_model_new_record(booking_series_admin_setup):
    # Create a new booking series with saved related objects
    organization = OrganizationFactory()  # Create and save an organization
    resource = ResourceFactory()  # Create and save a resource
    user = UserFactory()  # Create and save a user
    compensation = CompensationFactory()  # Create and save a compensation

    # Create a booking series with the saved related objects
    booking_series = BookingSeriesFactory.build(
        organization=organization,
        resource=resource,
        user=user,
        compensation=compensation,
    )

    # Call the save_model method
    booking_series_admin_setup["admin"].save_model(
        request=booking_series_admin_setup["request"],
        obj=booking_series,
        form=None,
        change=False,
    )

    # Check that the booking series was saved
    assert booking_series.pk is not None


@pytest.mark.django_db()
def test_save_model_existing_record(booking_series_admin_setup):
    # Create an existing booking series with some bookings
    booking_series = BookingSeriesFactory()
    booking1 = BookingFactory(booking_series=booking_series)
    booking2 = BookingFactory(booking_series=booking_series)

    # Change some attributes of the booking series
    booking_series.title = "New Title"
    booking_series.organization = OrganizationFactory()

    # Call the save_model method
    booking_series_admin_setup["admin"].save_model(
        request=booking_series_admin_setup["request"],
        obj=booking_series,
        form=None,
        change=True,
    )

    # Refresh the bookings from the database
    booking1.refresh_from_db()
    booking2.refresh_from_db()

    # Check that the bookings were updated with the new attributes
    assert booking1.title == "New Title"
    assert booking1.organization == booking_series.organization
    assert booking2.title == "New Title"
    assert booking2.organization == booking_series.organization


@pytest.mark.django_db()
def test_delete_bookings(booking_series_admin_setup):
    # Create a booking series with some bookings
    booking_series = BookingSeriesFactory()
    BookingFactory(booking_series=booking_series)
    BookingFactory(booking_series=booking_series)

    # Mock the queryset
    queryset = BookingSeries.objects.filter(id=booking_series.id)

    # Call the delete_bookings action
    booking_series_admin_setup["admin"].delete_bookings(
        booking_series_admin_setup["request"], queryset
    )

    # Check that all bookings for the booking series were deleted
    assert Booking.objects.filter(booking_series=booking_series).count() == 0


@pytest.mark.django_db()
@patch("re_sharing.bookings.admin.generate_bookings")
def test_generate_bookings(mock_generate_bookings, booking_series_admin_setup):
    # Create a booking series
    booking_series = BookingSeriesFactory()

    # Create saved related objects for the mock booking
    organization = OrganizationFactory()
    resource = ResourceFactory()
    user = UserFactory()
    compensation = CompensationFactory()

    # Create a mock booking with saved related objects
    mock_booking = BookingFactory.build(
        booking_series=booking_series,
        organization=organization,
        resource=resource,
        user=user,
        compensation=compensation,
    )

    # Mock the generate_bookings function to return our mock booking
    # But also make it save the booking to avoid the actual save in the admin method
    def side_effect(*args, **kwargs):
        mock_booking.save()
        return [mock_booking]

    mock_generate_bookings.side_effect = side_effect

    # Mock the queryset
    queryset = BookingSeries.objects.filter(id=booking_series.id)

    # Call the generate_bookings action
    booking_series_admin_setup["admin"].generate_bookings(
        booking_series_admin_setup["request"], queryset
    )

    # Check that generate_bookings was called with the correct arguments
    mock_generate_bookings.assert_called_once()

    # The first argument should be the booking series
    assert mock_generate_bookings.call_args[0][0] == booking_series

    # The second and third arguments should be datetime objects
    assert isinstance(mock_generate_bookings.call_args[0][1], timezone.datetime)
    assert isinstance(mock_generate_bookings.call_args[0][2], timezone.datetime)
