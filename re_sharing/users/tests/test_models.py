from re_sharing.organizations.models import BookingPermission
from re_sharing.organizations.tests.factories import BookingPermissionFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.resources.tests.factories import ResourceFactory
from re_sharing.users.models import User


def test_user_get_absolute_url(user: User):
    assert user.get_absolute_url() == f"/users/{user.slug}/"


def test_user_str_representation(user: User):
    assert str(user) == f"{user.first_name} {user.last_name}"


def test_user_get_organizations_of_user(user: User):
    # Create organizations and permissions
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()
    org3 = OrganizationFactory()

    # Give user confirmed permission for org1 and org2
    BookingPermissionFactory(
        user=user, organization=org1, status=BookingPermission.Status.CONFIRMED
    )
    BookingPermissionFactory(
        user=user, organization=org2, status=BookingPermission.Status.CONFIRMED
    )

    # Give user pending permission for org3 (should not be included)
    BookingPermissionFactory(
        user=user, organization=org3, status=BookingPermission.Status.PENDING
    )

    organizations = user.get_organizations_of_user()
    assert org1 in organizations
    assert org2 in organizations
    assert org3 not in organizations
    assert organizations.count() == 2  # noqa: PLR2004


def test_user_get_resources_includes_public_resources(user: User):
    # Create different types of resources
    public_resource = ResourceFactory(is_private=False)
    ResourceFactory(is_private=True)

    # For any authenticated user, public resources should be included
    resources = user.get_resources()
    assert public_resource in resources


def test_user_is_manager_true(user: User):
    # Create a manager for the user
    ManagerFactory(user=user)
    assert user.is_manager()


def test_user_is_manager_false(user: User):
    # User has no manager
    assert not user.is_manager()


def test_user_get_manager_exists(user: User):
    # Create a manager for the user
    manager = ManagerFactory(user=user)
    assert user.get_manager() == manager


def test_user_get_manager_none(user: User):
    # User has no manager
    assert user.get_manager() is None
