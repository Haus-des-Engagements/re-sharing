from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from roomsharing.users.models import User

from .forms import OrganizationForm
from .models import Organization
from .models import OrganizationMembership


@login_required
def list_organizations_view(request):
    user = request.user
    user_organizations = user.organizations.all()

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            new_org = form.save(commit=False)
            # add additional fields like user if necessary

            new_org.save()
            organization_membership = OrganizationMembership(
                user=user,
                organization=new_org,
                status=OrganizationMembership.Status.CONFIRMED,
            )
            organization_membership.save()

            return redirect("organizations:list-organizations")
    else:
        form = OrganizationForm()

    return render(
        request,
        "organizations/list_organizations.html",
        {"organizations": user_organizations, "form": form},
    )


@login_required
def show_organization_view(request, slug):
    organization = get_object_or_404(Organization, slug=slug)
    members = User.objects.filter(organizations__in=[organization])

    return render(
        request,
        "organizations/show_organization.html",
        {"organization": organization, "members": members},
    )
