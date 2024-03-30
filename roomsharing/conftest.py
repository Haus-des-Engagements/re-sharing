import pytest

from roomsharing.rooms.models import Room
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
