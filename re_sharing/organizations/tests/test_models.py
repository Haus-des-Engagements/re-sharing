from re_sharing.organizations.models import Organization


def test_organization_get_absolute_url(organization: Organization):
    assert organization.get_absolute_url() == f"/organizations/{organization.slug}/"


def test_is_deactivatable_only_when_confirmed(organization: Organization):
    organization.status = Organization.Status.CONFIRMED
    assert organization.is_deactivatable() is True

    organization.status = Organization.Status.PENDING
    assert organization.is_deactivatable() is False

    organization.status = Organization.Status.REJECTED
    assert organization.is_deactivatable() is False

    organization.status = Organization.Status.DEACTIVATED
    assert organization.is_deactivatable() is False


def test_is_activatable_only_when_deactivated(organization: Organization):
    organization.status = Organization.Status.DEACTIVATED
    assert organization.is_activatable() is True

    organization.status = Organization.Status.CONFIRMED
    assert organization.is_activatable() is False

    organization.status = Organization.Status.PENDING
    assert organization.is_activatable() is False

    organization.status = Organization.Status.REJECTED
    assert organization.is_activatable() is False
