from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from .forms import OrganizationForm
from .models import BookingPermission
from .models import Organization
from .services import create_organization
from .services import filter_organizations
from .services import show_organization
from .services import update_organization
from .services import user_has_admin_bookingpermission


def list_organizations_view(request):
    organization_name = request.GET.get("organization_name")
    organizations = filter_organizations(organization_name)

    context = {"organizations": organizations}
    if request.headers.get("HX-Request"):
        return render(
            request, "organizations/partials/list_organizations.html", context
        )

    return render(request, "organizations/list_organizations.html", context)


def show_organization_view(request, organization):
    organization, permitted_users, is_admin = show_organization(
        request.user, organization_slug=organization
    )
    context = {
        "organization": organization,
        "permitted_users": permitted_users,
        "is_admin": is_admin,
    }
    return render(request, "organizations/show_organization.html", context)


@login_required
def request_bookingpermission_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    bookingpermissions = BookingPermission.objects.filter(
        organization=organization
    ).filter(user=request.user)

    if bookingpermissions.exists():
        if bookingpermissions.first().status == BookingPermission.Status.PENDING:
            return HttpResponse(
                "You are already requested to become a member. Please wait patiently."
            )
        if bookingpermissions.first().status == BookingPermission.Status.CONFIRMED:
            return HttpResponse("You are already member of this organization.")
        if bookingpermissions.first().status == BookingPermission.Status.REJECTED:
            return HttpResponse("You have already been rejected by this organization.")

    bookingpermissions.create(
        user=request.user,
        organization=organization,
        status=BookingPermission.Status.PENDING,
        role=BookingPermission.Role.BOOKER,
    )
    return HttpResponse(
        "Successfully requested. "
        "You will be notified when your request is approved or denied."
    )


@login_required
def cancel_bookingpermission_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    bookingpermissions = BookingPermission.objects.filter(
        organization=organization
    ).filter(user__slug=user)

    if request.user.slug == user or user_has_admin_bookingpermission(
        request.user, organization
    ):
        if bookingpermissions.exists():
            bookingpermissions.first().delete()
            return HttpResponse("Booking permission has been cancelled.")
        return HttpResponse("Booking permission does not exist.")

    return HttpResponse(
        "You are not allowed to cancel this booking permission.",
        status=HTTPStatus.UNAUTHORIZED,
    )


@login_required
def delete_organization_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    if user_has_admin_bookingpermission(request.user, organization):
        organization.delete()
        messages.success(request, "Organization deleted successfully.")
        return redirect("organizations:list-organizations")

    return HttpResponse(
        "You are not allowed to delete this organization.",
        status=HTTPStatus.UNAUTHORIZED,
    )


@login_required
def confirm_bookingpermission_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    bookingpermission = (
        BookingPermission.objects.filter(organization=organization)
        .filter(user__slug=user)
        .first()
    )

    if bookingpermission and user_has_admin_bookingpermission(
        request.user, organization
    ):
        if bookingpermission.status == BookingPermission.Status.CONFIRMED:
            return HttpResponse("Booking permission has already been confirmed.")

        bookingpermission.status = BookingPermission.Status.CONFIRMED
        bookingpermission.save()
        return HttpResponse("Booking permission has been confirmed.")

    return HttpResponse(
        "You are not allowed to confirm this booking permission.",
        status=HTTPStatus.UNAUTHORIZED,
    )


@login_required
def promote_to_admin_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    bookingpermission = (
        BookingPermission.objects.filter(organization=organization)
        .filter(user__slug=user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .first()
    )

    if bookingpermission and user_has_admin_bookingpermission(
        request.user, organization
    ):
        bookingpermission.role = BookingPermission.Role.ADMIN
        bookingpermission.save()
        return HttpResponse("User has been promoted to admin.")

    return HttpResponse(
        "You are not allowed to promote.", status=HTTPStatus.UNAUTHORIZED
    )


@login_required
def demote_to_booker_view(request, organization, user):
    organization = get_object_or_404(Organization, slug=organization)
    bookingpermission = (
        BookingPermission.objects.filter(organization=organization)
        .filter(user__slug=user)
        .first()
    )

    if bookingpermission and user_has_admin_bookingpermission(
        request.user, organization
    ):
        bookingpermission.role = BookingPermission.Role.BOOKER
        bookingpermission.save()
        return HttpResponse("User has been demoted to booker.")

    return HttpResponse(
        "You are not allowed to demote.", status=HTTPStatus.UNAUTHORIZED
    )


@login_required
def create_organization_view(request):
    form = OrganizationForm()

    if request.method == "POST":
        form = OrganizationForm(request.POST, request.FILES)

        if form.is_valid():
            organization = create_organization(request.user, form)
            return redirect("organizations:show-organization", organization.slug)

    return render(request, "organizations/create_organization.html", {"form": form})


@login_required
def update_organization_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    if user_has_admin_bookingpermission(request.user, organization):
        form = OrganizationForm(instance=organization)
    else:
        raise PermissionDenied

    if request.method == "POST":
        form = OrganizationForm(request.POST, request.FILES, instance=organization)
        if form.is_valid():
            organization = update_organization(request.user, form, organization)
            messages.success(request, "Organization updated successfully.")
            return redirect("organizations:show-organization", organization.slug)

    return render(request, "organizations/create_organization.html", {"form": form})
