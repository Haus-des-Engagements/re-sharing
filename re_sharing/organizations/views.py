from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from re_sharing.providers.decorators import manager_required

from .forms import OrganizationForm
from .forms import OrganizationMessageForm
from .models import Organization
from .models import OrganizationGroup
from .models import OrganizationMessage
from .services import add_user_to_organization
from .services import cancel_booking_permission
from .services import confirm_booking_permission
from .services import create_organization
from .services import create_organizationmessage
from .services import demote_user_to_booker
from .services import filter_organizations
from .services import manager_cancel_organization
from .services import manager_confirm_organization
from .services import manager_filter_organizations_list
from .services import promote_user_to_admin
from .services import request_booking_permission
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
@manager_required
def manager_list_organizations_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the organizations for a manager so that they can be confirmed or cancelled.
    Only shows organizations that are part of the organization_groups that the
    manager is assigned to.
    """
    status = request.GET.get("status") or "all"
    group = request.GET.get("group") or "all"
    search = request.GET.get("search")

    # Get the manager object for the current user
    manager = request.user.get_manager()

    # Filter organizations based on the manager's assigned organization_groups
    organizations = manager_filter_organizations_list(status, group, manager, search)

    # Get only the organization groups that the manager has access to
    available_groups = OrganizationGroup.objects.all()
    if manager and manager.organization_groups.exists():
        available_groups = manager.organization_groups.all()

    context = {
        "organizations": organizations,
        "statuses": Organization.Status.choices,
        "groups": available_groups,
    }

    if request.headers.get("HX-Request"):
        return render(
            request, "organizations/partials/manager_list_organizations.html", context
        )

    return render(request, "organizations/manager_list_organizations.html", context)


@require_http_methods(["PATCH"])
@manager_required
def manager_cancel_organization_view(request, organization_slug):
    organization = manager_cancel_organization(request.user, organization_slug)

    return render(
        request,
        "organizations/partials/manager_organization_item.html",
        {"organization": organization},
    )


@require_http_methods(["PATCH"])
@manager_required
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


@login_required
def organization_permission_view(request, organization):
    """
    HTTP layer for permission creation: self-request and admin-add
    """
    organization_obj = get_object_or_404(Organization, slug=organization)
    action = request.POST.get("action", "request")

    # HTTP: Route to appropriate service handler
    if action == "request":
        return _handle_permission_request(request, organization_obj)
    if action == "add-user":
        return _handle_add_user(request, organization_obj)
    return HttpResponse("Invalid action", status=HTTPStatus.BAD_REQUEST)


def _handle_permission_request(request, organization):
    """Handle user self-requesting permission"""
    try:
        message = request_booking_permission(request.user, organization)
        return HttpResponse(message)
    except (PermissionDenied, ValueError) as e:
        return HttpResponse(str(e), status=HTTPStatus.BAD_REQUEST)


def _handle_add_user(request, organization):
    """Handle admin adding a user to organization"""
    email = request.POST.get("email")
    role = request.POST.get("role")

    try:
        message = add_user_to_organization(organization, email, role, request.user)
        messages.success(request, message)
    except PermissionDenied as e:
        messages.error(request, str(e))
    except ValueError as e:
        messages.error(request, str(e))
    except Exception:  # noqa: BLE001
        messages.error(request, "An error occurred while adding the user.")

    return redirect("organizations:show-organization", organization=organization.slug)


@login_required
def organization_permission_management_view(request, organization, user):
    """Handles permission management: confirm/cancel/promote/demote"""
    organization_obj = get_object_or_404(Organization, slug=organization)
    action = request.POST.get("action")

    if not action:
        return HttpResponse("Action is required", status=HTTPStatus.BAD_REQUEST)

    # Action dispatch
    if action == "confirm":
        return _confirm_permission(request, organization_obj, user)
    if action == "cancel":
        return _cancel_permission(request, organization_obj, user)
    if action == "promote":
        return _promote_to_admin(request, organization_obj, user)
    if action == "demote":
        return _demote_to_booker(request, organization_obj, user)
    return HttpResponse("Invalid action", status=HTTPStatus.BAD_REQUEST)


def _confirm_permission(request, organization, user_slug):
    """Confirm a booking permission request"""
    try:
        message = confirm_booking_permission(organization, user_slug, request.user)
        return HttpResponse(message)
    except PermissionDenied as e:
        return HttpResponse(str(e), status=HTTPStatus.UNAUTHORIZED)


def _cancel_permission(request, organization, user_slug):
    """Cancel a booking permission"""
    try:
        message = cancel_booking_permission(organization, user_slug, request.user)
        return HttpResponse(message)
    except PermissionDenied as e:
        return HttpResponse(str(e), status=HTTPStatus.UNAUTHORIZED)


def _promote_to_admin(request, organization, user_slug):
    """Promote a user to admin role"""
    try:
        message = promote_user_to_admin(organization, user_slug, request.user)
        return HttpResponse(message)
    except PermissionDenied as e:
        return HttpResponse(str(e), status=HTTPStatus.UNAUTHORIZED)


def _demote_to_booker(request, organization, user_slug):
    """Demote a user to booker role"""
    try:
        message = demote_user_to_booker(organization, user_slug, request.user)
        return HttpResponse(message)
    except PermissionDenied as e:
        return HttpResponse(str(e), status=HTTPStatus.UNAUTHORIZED)
