import pytest

from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.models import ResourceImage
from re_sharing.resources.models import create_resourceimage_path
from re_sharing.resources.models import select_default_storage
from re_sharing.resources.tests.factories import CompensationFactory
from re_sharing.resources.tests.factories import ResourceFactory


# Test Resource model methods
@pytest.mark.django_db()
def test_resource_is_bookable_by_organization():
    # Create a resource
    resource = ResourceFactory(is_private=True)

    # Create organizations and organization groups
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()
    org_group = OrganizationGroupFactory()

    # Add org1 to the organization group
    org_group.organizations_of_organizationgroups.add(org1)

    # Set the organization group for the resource
    org_group.bookable_private_resources.add(resource)

    # Test that org1 can book the resource
    assert resource.is_bookable_by_organization(org1) is True

    # Test that org2 cannot book the resource
    assert resource.is_bookable_by_organization(org2) is False

    # Test that when no organization groups are specified, any organization can book
    resource2 = ResourceFactory()
    assert resource2.is_bookable_by_organization(org1) is True
    assert resource2.is_bookable_by_organization(org2) is True


@pytest.mark.django_db()
def test_resource_get_bookable_compensations():
    # Create a resource
    resource = ResourceFactory()

    # Create an organization
    org = OrganizationFactory()

    # Create compensations
    comp1 = CompensationFactory(name="Comp1")
    comp1.resource.add(resource)

    comp2 = CompensationFactory(name="Comp2")
    comp2.resource.add(resource)

    # Create a compensation with organization group restriction
    comp3 = CompensationFactory(name="Comp3")
    comp3.resource.add(resource)
    org_group = OrganizationGroupFactory()
    comp3.organization_groups.add(org_group)

    # Test that all compensations are returned when no org groups are specified
    bookable_comps = resource.get_bookable_compensations(org)
    assert comp1 in bookable_comps
    assert comp2 in bookable_comps
    assert comp3 not in bookable_comps

    # Add the organization to the organization group
    org_group.organizations_of_organizationgroups.add(org)

    # Test that all compensations are now returned
    bookable_comps = resource.get_bookable_compensations(org)
    assert comp1 in bookable_comps
    assert comp2 in bookable_comps
    assert comp3 in bookable_comps


# Test ResourceImage model methods
@pytest.mark.django_db()
def test_resourceimage_str():
    # Create a resource
    resource = ResourceFactory(name="Test Resource")

    # Create a resource image
    resource_image = ResourceImage(resource=resource, description="Test Description")

    # Test the __str__ method
    assert str(resource_image) == "Test Resource: Test Description"


@pytest.mark.django_db()
def test_resourceimage_get_absolute_url():
    # Create a resource
    resource = ResourceFactory(slug="test-resource")

    # Create a resource image
    resource_image = ResourceImage(resource=resource, description="Test Description")

    # Test the get_absolute_url method
    assert resource_image.get_absolute_url() == f"/resources/{resource.slug}/"


# Test Compensation model methods
@pytest.mark.django_db()
def test_compensation_str():
    # Test with hourly rate
    comp1 = CompensationFactory(name="Comp1", hourly_rate=10)
    assert str(comp1) == "Comp1 (10 €)"

    # Test without hourly rate
    comp2 = CompensationFactory(name="Comp2", hourly_rate=None)
    assert str(comp2) == "Comp2"


@pytest.mark.django_db()
def test_compensation_is_bookable_by_organization():
    # Create a compensation
    comp = CompensationFactory()

    # Create organizations and organization groups
    org1 = OrganizationFactory()
    org2 = OrganizationFactory()
    org_group = OrganizationGroupFactory()

    # Add org1 to the organization group
    org_group.organizations_of_organizationgroups.add(org1)

    # Test that when no organization groups are specified, any organization can book
    assert comp.is_bookable_by_organization(org1) is True
    assert comp.is_bookable_by_organization(org2) is True

    # Set the organization group for the compensation
    comp.organization_groups.add(org_group)
    comp.refresh_from_db()

    # Test that org1 can book the compensation
    assert comp.is_bookable_by_organization(org1) is True

    # Test that org2 cannot book the compensation
    assert comp.is_bookable_by_organization(org2) is False


# Test utility functions
@pytest.mark.django_db()
def test_create_resourceimage_path():
    # Create a resource
    resource = ResourceFactory(name="Test Resource")

    # Create a resource image
    resource_image = ResourceImage(resource=resource, description="Test Description")

    # Test the create_resourceimage_path function
    path = create_resourceimage_path(resource_image, "test.jpg")
    assert path.startswith("resource_images/")
    assert path.endswith("test.jpg")


@pytest.mark.django_db()
def test_select_default_storage():
    # Test the select_default_storage function
    storage = select_default_storage()
    assert storage is not None
