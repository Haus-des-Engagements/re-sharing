from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.db.models import OuterRef
from django.db.models import Subquery
from django.http import HttpResponse
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from roomsharing.users.models import User

from .forms import OrganizationForm
from .forms import OrganizationsListFilter
from .models import Membership
from .models import Organization


@login_required
def list_organizations_view(request):
    filter_form = OrganizationsListFilter(request.POST or None)
    user = request.user
    membership = Membership.objects.filter(
        user=user, organization=OuterRef("pk")
    ).values("status")[:1]
    organizations = Organization.objects.annotate(
        membership_status=Subquery(membership)
    )

    if request.method == "POST":
        form = OrganizationForm(request.POST)
        if form.is_valid():
            new_org = form.save(commit=False)

            new_org.save()
            organization_membership = Membership(
                user=user,
                organization=new_org,
                status=Membership.Status.CONFIRMED,
                role=Membership.Role.ADMIN,
            )
            organization_membership.save()

            return redirect("organizations:list-organizations")
    else:
        form = OrganizationForm()

    return render(
        request,
        "organizations/list_organizations.html",
        {"organizations": organizations, "form": form, "filter-form": filter_form},
    )


def filter_organizations_view(request):
    form = OrganizationsListFilter(request.POST or None)
    organizations = Organization.objects.all()

    if form.is_valid():
        name = form.cleaned_data.get("name")
        if name:
            organizations = organizations.filter(name__icontains=name)

        return render(
            request,
            "organizations/partials/list_filter_organizations.html",
            {"organizations": organizations, "form": form},
        )

    return HttpResponse(
        f'<p class="error">Your form submission was unsuccessful. '
        f"Please would you correct the errors? The current errors: {form.errors}</p>",
    )


def user_is_member(user, organization):
    return (
        Membership.objects.filter(user=user)
        .filter(organization=organization)
        .filter(status=Membership.Status.CONFIRMED)
        .exists()
    )


def user_is_admin_member(user, organization):
    return (
        Membership.objects.filter(user=user)
        .filter(organization=organization)
        .filter(status=Membership.Status.CONFIRMED)
        .filter(role=Membership.Role.ADMIN)
        .exists()
    )


@login_required
def show_organization_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    members = []
    is_admin = False

    if user_is_admin_member(request.user, organization):
        memberships = Membership.objects.filter(organization=organization)
        members = (
            User.objects.filter(user_of_membership__in=memberships)
            .annotate(membership_status=F("user_of_membership__status"))
            .annotate(membership_role=F("user_of_membership__role"))
        )
        is_admin = True

    elif user_is_member(request.user, organization):
        memberships = Membership.objects.filter(organization=organization)
        members = User.objects.filter(user_of_membership__in=memberships).values(
            "first_name", "last_name", "email"
        )

    return render(
        request,
        "organizations/show_organization.html",
        {"organization": organization, "members": members, "is_admin": is_admin},
    )


@login_required
def request_membership_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    memberships = Membership.objects.filter(organization=organization).filter(
        user=request.user
    )

    if memberships.exists():
        if memberships.first().status == Membership.Status.PENDING:
            return HttpResponse(
                "You are already requested to become a member. Please wait patiently."
            )
        if memberships.first().status == Membership.Status.CONFIRMED:
            return HttpResponse("You are already member of this organization.")
        if memberships.first().status == Membership.Status.REJECTED:
            return HttpResponse("You have already been rejected by this organization.")

    memberships.create(
        user=request.user,
        organization=organization,
        status=Membership.Status.PENDING,
        role=Membership.Role.BOOKER,
    )
    return HttpResponse(
        "Successfully requested. "
        "You will be notified when your request is approved or denied."
    )


@login_required
def cancel_membership_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    memberships = Membership.objects.filter(organization=organization).filter(
        user__slug=user
    )

    if request.user.slug == user or user_is_admin_member(request.user, organization):
        if memberships.exists():
            memberships.first().delete()
            return HttpResponse("Membership has been cancelled.")
        return HttpResponse("Membership does not exist.")

    return HttpResponse(
        "You are not allowed to cancel this membership.", status=HTTPStatus.UNAUTHORIZED
    )


@login_required
def delete_organization_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    if user_is_admin_member(request.user, organization):
        organization.delete()
        messages.success(request, "Organization deleted successfully.")
        return redirect("organizations:list-organizations")

    return HttpResponseNotAllowed("You are not allowed to delete this organization.")


@login_required
def confirm_membership_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    membership = (
        Membership.objects.filter(organization=organization)
        .filter(user__slug=user)
        .first()
    )

    if membership and user_is_admin_member(request.user, organization):
        if membership.status == Membership.Status.CONFIRMED:
            return HttpResponse("Membership has already been confirmed.")

        membership.status = Membership.Status.CONFIRMED
        membership.save()
        return HttpResponse("Membership has been confirmed.")

    return HttpResponse(
        "You are not allowed to confirm this membership.",
        status=HTTPStatus.UNAUTHORIZED,
    )


@login_required
def promote_to_admin_membership_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    membership = (
        Membership.objects.filter(organization=organization)
        .filter(user__slug=user)
        .filter(status=Membership.Status.CONFIRMED)
        .first()
    )

    if membership and user_is_admin_member(request.user, organization):
        membership.role = Membership.Role.ADMIN
        membership.save()
        return HttpResponse("Member has been promoted to admin.")

    return HttpResponse(
        "You are not allowed to promote.", status=HTTPStatus.UNAUTHORIZED
    )


@login_required
def demote_to_booker_membership_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    membership = (
        Membership.objects.filter(organization=organization)
        .filter(user__slug=user)
        .first()
    )

    if membership and user_is_admin_member(request.user, organization):
        membership.role = Membership.Role.BOOKER
        membership.save()
        return HttpResponse("Member has been demoted to booker.")

    return HttpResponse(
        "You are not allowed to demote.", status=HTTPStatus.UNAUTHORIZED
    )
