from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from .models import Organization


@login_required
def my_organization_list(request):
    user = request.user
    user_organizations = user.organizations.all()
    return render(
        request,
        "organizations/organization_list.html",
        {"organizations": user_organizations},
    )


@permission_required("is_staff")
def organization_list(request):
    organizations = Organization.objects.all()
    return render(
        request,
        "organizations/organization_list.html",
        {"organizations": organizations},
    )


def organization_detail(request, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)
    return render(
        request,
        "organizations/organization_detail.html",
        {"organization": organization},
    )
