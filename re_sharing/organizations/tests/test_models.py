from re_sharing.organizations.models import Organization


def test_organization_get_absolute_url(organization: Organization):
    assert organization.get_absolute_url() == f"/organizations/{organization.slug}/"
