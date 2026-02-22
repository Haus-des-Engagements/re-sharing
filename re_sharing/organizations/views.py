from http import HTTPStatus

import django_filters
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from neapolitan.views import CRUDView

from re_sharing.providers.decorators import ManagerRequiredMixin
from re_sharing.providers.decorators import manager_required

from .forms import OrganizationForm
from .forms import OrganizationMessageForm
from .models import BookingPermission
from .models import EmailTemplate
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
            request, "organizations/list_organizations.html#organization-list", context
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
        if "organization_groups" in form.errors:
            messages.error(
                request,
                _("Please select at least one organization group."),
            )

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
        if "organization_groups" in form.errors:
            messages.error(
                request,
                _("Please select at least one organization group."),
            )

    return render(
        request,
        "organizations/create_organization.html",
        {"form": form, "organization": organization},
    )


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
            request,
            "organizations/manager_list_organizations.html#organization-list",
            context,
        )

    return render(request, "organizations/manager_list_organizations.html", context)


@require_http_methods(["PATCH"])
@manager_required
def manager_cancel_organization_view(request, organization_slug):
    organization = manager_cancel_organization(request.user, organization_slug)

    return render(
        request,
        "organizations/manager_list_organizations.html#organization-item",
        {"organization": organization},
    )


@require_http_methods(["PATCH"])
@manager_required
def manager_confirm_organization_view(request, organization_slug):
    organization = manager_confirm_organization(request.user, organization_slug)
    return render(
        request,
        "organizations/manager_list_organizations.html#organization-item",
        {"organization": organization},
    )


@require_http_methods(["PATCH", "POST"])
@manager_required
def manager_permanent_code_action_view(request, organization_slug):
    """Handle permanent code actions: create, invalidate, renew."""
    from re_sharing.resources.services_permanent_code import (
        create_permanent_code_for_organization,
    )
    from re_sharing.resources.services_permanent_code import invalidate_permanent_code
    from re_sharing.resources.services_permanent_code import renew_permanent_code

    action = request.POST.get("action")
    organization = get_object_or_404(Organization, slug=organization_slug)

    try:
        if action == "create":
            create_permanent_code_for_organization(organization_slug, request.user)

        elif action == "invalidate":
            permanent_code_id = request.POST.get("permanent_code_id")
            validity_end_str = request.POST.get("validity_end", "")

            if not permanent_code_id:
                return HttpResponseBadRequest("Missing permanent_code_id")

            # Parse datetime and make timezone-aware
            # Empty string means invalidate immediately
            if validity_end_str:
                from dateutil.parser import isoparse

                validity_end = isoparse(validity_end_str)
                # Make timezone-aware if naive
                if timezone.is_naive(validity_end):
                    validity_end = timezone.make_aware(validity_end)
            else:
                # Empty validity_end means invalidate immediately
                validity_end = timezone.now()

            invalidate_permanent_code(
                int(permanent_code_id), validity_end, request.user
            )

        elif action == "renew":
            permanent_code_id = request.POST.get("permanent_code_id")
            if not permanent_code_id:
                return HttpResponseBadRequest("Missing permanent_code_id")

            renew_permanent_code(int(permanent_code_id), request.user)

        else:
            return HttpResponseBadRequest(f"Unknown action: {action}")

    except ValidationError as e:
        return HttpResponseBadRequest(str(e))

    # Re-fetch organization with annotations for the template
    from re_sharing.organizations.services import manager_filter_organizations_list

    manager = request.user.get_manager()
    organizations = manager_filter_organizations_list("all", "all", manager, None)
    organization = organizations.get(slug=organization_slug)

    return render(
        request,
        "organizations/manager_list_organizations.html#organization-item",
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
        "organizations/show_organization_messages.html#organization-message",
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


# ============================================================================
# Neapolitan CRUD Views
# ============================================================================


class BookingPermissionFilterSet(django_filters.FilterSet):
    """Custom filterset for BookingPermission with all fields and user search."""

    # User-related filters
    user__first_name = django_filters.CharFilter(
        lookup_expr="icontains", label="First Name"
    )
    user__last_name = django_filters.CharFilter(
        lookup_expr="icontains", label="Last Name"
    )
    user__email = django_filters.CharFilter(lookup_expr="icontains", label="Email")

    class Meta:
        model = BookingPermission
        fields = [
            "user",
            "user__first_name",
            "user__last_name",
            "user__email",
            "organization",
            "role",
            "status",
        ]


class BookingPermissionView(LoginRequiredMixin, ManagerRequiredMixin, CRUDView):
    """CRUD view for managing booking permissions."""

    model = BookingPermission
    fields = ["user", "organization", "role", "status"]
    filterset_class = BookingPermissionFilterSet

    def get_queryset(self):
        """
        Filter BookingPermissions to only show permissions for organizations
        the manager has access to.
        """
        manager = self.request.user.get_manager()
        if manager.organization_groups.exists():
            # Get all organization groups the manager has access to
            allowed_groups = manager.organization_groups.all()
            # Filter organizations that belong to these groups
            allowed_organizations = Organization.objects.filter(
                organization_groups__in=allowed_groups
            ).distinct()
            # Return booking permissions for these organizations
            return BookingPermission.objects.filter(
                organization__in=allowed_organizations
            ).select_related("user", "organization")
        # If manager has no group restrictions, show all
        return BookingPermission.objects.all().select_related("user", "organization")

    def get_success_url(self):
        from django.urls import reverse

        return reverse("organizations:bookingspermission-list")


class EmailTemplateFilterSet(django_filters.FilterSet):
    """Custom filterset for EmailTemplate with all fields."""

    class Meta:
        model = EmailTemplate
        fields = ["email_type", "active"]


@method_decorator(staff_member_required, name="dispatch")
class EmailTemplateView(LoginRequiredMixin, CRUDView):
    """CRUD view for managing email templates."""

    model = EmailTemplate
    fields = ["email_type", "subject", "body", "active"]
    filterset_class = EmailTemplateFilterSet

    def get_success_url(self):
        from django.urls import reverse

        return reverse("organizations:emailtemplate-list")


@manager_required
def custom_organization_email_view(request: HttpRequest) -> HttpResponse:
    """
    View for composing and previewing custom emails to filtered organizations.
    Managers can filter organizations and see which ones will receive the email.
    """
    from re_sharing.organizations.selectors import get_filtered_organizations

    organizations = []
    filter_params = {}

    if request.method == "GET":
        # Get filter parameters
        include_groups = request.GET.getlist("include_groups")
        exclude_groups = request.GET.getlist("exclude_groups")
        min_bookings = request.GET.get("min_bookings")
        months = request.GET.get("months")
        max_amount = request.GET.get("max_amount")

        # Convert to appropriate types
        include_groups = [int(g) for g in include_groups if g]
        exclude_groups = [int(g) for g in exclude_groups if g]
        min_bookings = int(min_bookings) if min_bookings else None
        months = int(months) if months else None
        max_amount = float(max_amount) if max_amount else None

        # Store filter params for later use
        if min_bookings is not None and months is not None:
            filter_params = {
                "min_bookings": min_bookings,
                "months": months,
            }

        # Get filtered organizations if any filters applied
        if include_groups or exclude_groups or (min_bookings and months) or max_amount:
            organizations = get_filtered_organizations(
                include_groups=include_groups if include_groups else None,
                exclude_groups=exclude_groups if exclude_groups else None,
                min_bookings=min_bookings,
                months=months,
                max_amount=max_amount,
            )

    # Get all organization groups for the filter form
    organization_groups = OrganizationGroup.objects.all()

    context = {
        "organizations": organizations,
        "organization_groups": organization_groups,
        "filter_params": filter_params,
        "selected_include_groups": request.GET.getlist("include_groups"),
        "selected_exclude_groups": request.GET.getlist("exclude_groups"),
        "min_bookings": request.GET.get("min_bookings", ""),
        "months": request.GET.get("months", ""),
        "max_amount": request.GET.get("max_amount", ""),
    }

    return render(request, "organizations/custom_organization_email.html", context)


@manager_required
@require_http_methods(["POST"])
def send_custom_organization_email_view(request: HttpRequest) -> HttpResponse:
    """
    View for sending custom emails to filtered organizations.
    """
    from re_sharing.organizations.mails import send_custom_organization_email
    from re_sharing.organizations.selectors import get_filtered_organizations

    # Get filter parameters
    include_groups = request.POST.getlist("include_groups")
    exclude_groups = request.POST.getlist("exclude_groups")
    min_bookings = request.POST.get("min_bookings")
    months = request.POST.get("months")
    max_amount = request.POST.get("max_amount")
    selected_org_ids = request.POST.getlist("selected_orgs")

    # Get email content
    subject_template = request.POST.get("subject", "")
    body_template = request.POST.get("body", "")

    if not subject_template or not body_template:
        messages.error(request, "Subject and body are required.")
        return redirect("organizations:custom-organization-email")

    if not selected_org_ids:
        messages.error(request, "Please select at least one organization.")
        return redirect("organizations:custom-organization-email")

    # Convert to appropriate types
    include_groups = [int(g) for g in include_groups if g]
    exclude_groups = [int(g) for g in exclude_groups if g]
    min_bookings = int(min_bookings) if min_bookings else None
    months = int(months) if months else None
    max_amount = float(max_amount) if max_amount else None
    selected_org_ids = [int(org_id) for org_id in selected_org_ids]

    # Build filter context
    filter_context = {}
    if min_bookings is not None and months is not None:
        filter_context = {
            "min_bookings": min_bookings,
            "months": months,
        }

    # Get filtered organizations
    organizations = get_filtered_organizations(
        include_groups=include_groups if include_groups else None,
        exclude_groups=exclude_groups if exclude_groups else None,
        min_bookings=min_bookings,
        months=months,
        max_amount=max_amount,
    )

    # Filter to only selected organizations
    organizations = organizations.filter(id__in=selected_org_ids)

    if not organizations.exists():
        messages.warning(request, "No organizations match the selected filters.")
        return redirect("organizations:custom-organization-email")

    # Send emails
    result = send_custom_organization_email(
        organizations=organizations,
        subject_template=subject_template,
        body_template=body_template,
        filter_context=filter_context if filter_context else None,
    )

    messages.success(
        request,
        f"Successfully sent {result['sent_count']} email(s) to organizations.",
    )

    return redirect("organizations:custom-organization-email")
