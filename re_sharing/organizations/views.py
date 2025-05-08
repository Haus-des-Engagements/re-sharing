from http import HTTPStatus

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from re_sharing.users.models import User

from .forms import OrganizationForm
from .forms import OrganizationMessageForm
from .models import BookingPermission
from .models import Organization
from .models import OrganizationGroup
from .models import OrganizationMessage
from .services import create_organization
from .services import create_organizationmessage
from .services import filter_organizations
from .services import manager_cancel_organization
from .services import manager_confirm_organization
from .services import manager_filter_organizations_list
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

    # Get organization messages
    organization_messages = OrganizationMessage.objects.filter(
        organization=organization
    ).order_by("-created")

    context = {
        "organization": organization,
        "permitted_users": permitted_users,
        "is_admin": is_admin,
        "organization_messages": organization_messages,
        "message_form": OrganizationMessageForm()
        if request.user.is_authenticated
        else None,
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
def add_user_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)

    if not user_has_admin_bookingpermission(request.user, organization):
        raise PermissionDenied

    if request.method == "POST":
        email = request.POST.get("email")
        role = request.POST.get("role")

        if not email or not role:
            messages.error(request, "Email and role are required.")
            return redirect(
                "organizations:show-organization", organization=organization.slug
            )

        try:
            # Check if user exists by email
            user = User.objects.get(email=email)
            # Create or get the BookingPermission
            booking_permission, created = BookingPermission.objects.get_or_create(
                user=user,
                organization=organization,
                defaults={
                    "status": BookingPermission.Status.CONFIRMED,
                    "role": BookingPermission.Role.ADMIN
                    if role == "admin"
                    else BookingPermission.Role.BOOKER,
                },
            )
            if created:
                messages.success(request, f"{user.email} was successfully added!")
            else:
                messages.info(request, f"{user.email} already has permissions.")
        except User.DoesNotExist:
            messages.error(request, f"No user found with email: {email}")

    return redirect("organizations:show-organization", organization=organization.slug)


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
    form = OrganizationForm(user=request.user)

    if request.method == "POST":
        form = OrganizationForm(
            data=request.POST, files=request.FILES, user=request.user
        )

        if form.is_valid():
            organization = create_organization(request.user, form)
            return redirect("organizations:show-organization", organization.slug)

    return render(request, "organizations/create_organization.html", {"form": form})


@login_required
def update_organization_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    if request.method == "GET":
        if user_has_admin_bookingpermission(request.user, organization):
            form = OrganizationForm(instance=organization, user=request.user)
        else:
            raise PermissionDenied

    if request.method == "POST":
        form = OrganizationForm(
            files=request.FILES,
            data=request.POST,
            instance=organization,
            user=request.user,
        )
        if form.is_valid():
            organization = update_organization(request.user, form, organization)
            messages.success(request, "Organization updated successfully.")
            return redirect("organizations:show-organization", organization.slug)

    return render(request, "organizations/create_organization.html", {"form": form})


@require_http_methods(["GET"])
@staff_member_required
def manager_list_organizations_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the organizations for a manager so that they can be confirmed or cancelled
    """
    status = request.GET.get("status") or "all"
    group = request.GET.get("group") or "all"

    organizations = manager_filter_organizations_list(status, group)

    context = {
        "organizations": organizations,
        "statuses": Organization.Status.choices,
        "groups": OrganizationGroup.objects.all(),
    }

    if request.headers.get("HX-Request"):
        return render(
            request, "organizations/partials/manager_list_organizations.html", context
        )

    return render(request, "organizations/manager_list_organizations.html", context)


@require_http_methods(["PATCH"])
@staff_member_required
def manager_cancel_organization_view(request, organization_slug):
    organization = manager_cancel_organization(request.user, organization_slug)

    return render(
        request,
        "organizations/partials/manager_organization_item.html",
        {"organization": organization},
    )


@require_http_methods(["PATCH"])
@staff_member_required
def manager_confirm_organization_view(request, organization_slug):
    organization = manager_confirm_organization(request.user, organization_slug)
    return render(
        request,
        "organizations/partials/manager_organization_item.html",
        {"organization": organization},
    )


@require_http_methods(["GET"])
@login_required
def show_organization_messages_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)

    if (
        not user_has_admin_bookingpermission(request.user, organization)
        and not request.user.is_staff
    ):
        raise PermissionDenied

    # Get organization messages
    organization_messages = OrganizationMessage.objects.filter(
        organization=organization
    ).order_by("-created")

    context = {
        "organization": organization,
        "organization_messages": organization_messages,
        "message_form": OrganizationMessageForm(),
    }
    return render(request, "organizations/show_organization_messages.html", context)


@require_http_methods(["POST"])
@login_required
def create_organizationmessage_view(request, slug):
    form = OrganizationMessageForm(data=request.POST)
    organizationmessage = create_organizationmessage(slug, form, request.user)

    return render(
        request,
        "organizations/partials/show_organizationmessage.html",
        {"message": organizationmessage},
    )
