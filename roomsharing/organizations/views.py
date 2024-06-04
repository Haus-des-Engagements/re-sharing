from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from .models import Organization


@login_required
def list_organizations_view(request):
    user = request.user
    user_organizations = user.organizations.all()
    return render(
        request,
        "organizations/list_organizations.html",
        {"organizations": user_organizations},
    )


def show_organization_view(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    return render(
        request,
        "organizations/show_organization.html",
        {"organization": organization},
    )
