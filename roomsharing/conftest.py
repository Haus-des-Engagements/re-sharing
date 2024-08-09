import pytest

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import RecurrenceRule
from roomsharing.bookings.tests.factories import BookingFactory
from roomsharing.bookings.tests.factories import RecurrenceRuleFactory
from roomsharing.organizations.models import Organization
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.rooms.models import Access
from roomsharing.rooms.models import AccessCode
from roomsharing.rooms.models import Room
from roomsharing.rooms.tests.factories import AccessCodeFactory
from roomsharing.rooms.tests.factories import AccessFactory
from roomsharing.rooms.tests.factories import RoomFactory
from roomsharing.users.models import User
from roomsharing.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture()
def user(db) -> User:
    return UserFactory()


@pytest.fixture()
def room(db) -> Room:
    return RoomFactory()


@pytest.fixture()
def booking(db) -> Booking:
    return BookingFactory()


@pytest.fixture()
def organization(db) -> Organization:
    return OrganizationFactory()


@pytest.fixture()
def access(db) -> Access:
    return AccessFactory()


@pytest.fixture()
def access_code(db) -> AccessCode:
    return AccessCodeFactory()


@pytest.fixture()
def recurrence_rule(db) -> RecurrenceRule:
    return RecurrenceRuleFactory()
