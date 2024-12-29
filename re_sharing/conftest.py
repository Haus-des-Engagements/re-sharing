import pytest

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import BookingSeries
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import BookingSeriesFactory
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.models import Access
from re_sharing.resources.models import AccessCode
from re_sharing.resources.models import Compensation
from re_sharing.resources.models import Resource
from re_sharing.resources.tests.factories import AccessCodeFactory
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.models import User
from re_sharing.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture()
def user(db) -> User:
    return UserFactory()


@pytest.fixture()
def resource(db) -> Resource:
    return ResourceFactory()


@pytest.fixture()
def booking(db) -> Booking:
    return BookingFactory()


@pytest.fixture()
def organization(db) -> Organization:
    return OrganizationFactory()


@pytest.fixture()
def compensation(db) -> Compensation:
    return CompensationFactory()


@pytest.fixture()
def access(db) -> Access:
    return AccessFactory()


@pytest.fixture()
def access_code(db) -> AccessCode:
    return AccessCodeFactory()


@pytest.fixture()
def booking_series(db) -> BookingSeries:
    return BookingSeriesFactory()
