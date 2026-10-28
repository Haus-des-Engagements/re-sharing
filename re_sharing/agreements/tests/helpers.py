from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.users.tests.factories import UserFactory


def make_admin(organization, **kwargs):
    user = UserFactory(**kwargs)
    BookingPermissionFactory(
        user=user,
        organization=organization,
        role=BookingPermission.Role.ADMIN,
        status=BookingPermission.Status.CONFIRMED,
    )
    return user


def make_booker(organization):
    user = UserFactory()
    BookingPermissionFactory(
        user=user,
        organization=organization,
        role=BookingPermission.Role.BOOKER,
        status=BookingPermission.Status.CONFIRMED,
    )
    return user


def make_manager(*groups):
    user = UserFactory()
    ManagerFactory(user=user, organization_groups=list(groups))
    return user
