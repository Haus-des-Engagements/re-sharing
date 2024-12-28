import pytest

from re_sharing.bookings.models import Booking
from re_sharing.bookings.models import RecurrenceRule
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.bookings.tests.factories import RecurrenceRuleFactory
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.rooms.models import Access
from re_sharing.rooms.models import AccessCode
from re_sharing.rooms.models import Compensation
from re_sharing.rooms.models import Room
from re_sharing.rooms.tests.factories import AccessCodeFactory
from re_sharing.rooms.tests.factories import AccessFactory
from re_sharing.rooms.tests.factories import CompensationFactory
from re_sharing.rooms.tests.factories import RoomFactory
from re_sharing.users.models import User
from re_sharing.users.tests.factories import UserFactory


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
def compensation(db) -> Compensation:
    return CompensationFactory()


@pytest.fixture()
def access(db) -> Access:
    return AccessFactory()


@pytest.fixture()
def access_code(db) -> AccessCode:
    return AccessCodeFactory()


@pytest.fixture()
def recurrence_rule(db) -> RecurrenceRule:
    return RecurrenceRuleFactory()
