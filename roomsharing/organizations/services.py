from roomsharing.organizations.models import Organization


def filter_organizations(organization_name):
    organizations = Organization.objects.all()

    if organization_name:
        organizations = organizations.filter(name__icontains=organization_name)
    return organizations
