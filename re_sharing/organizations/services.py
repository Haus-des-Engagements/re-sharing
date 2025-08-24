from http import HTTPStatus

import requests
from auditlog.context import set_actor
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.models import F
from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404

from re_sharing.users.models import User
from re_sharing.utils.models import BookingStatus

from .models import BookingPermission
from .models import Organization
from .models import OrganizationGroup
from .models import OrganizationMessage


class InvalidOrganizationOperationError(Exception):
    def __init__(self):
        self.message = "You cannot perform this action."
        self.status_code = HTTPStatus.BAD_REQUEST


def filter_organizations(organization_name):
    organizations = Organization.objects.filter(is_public=True)

    if organization_name:
        organizations = organizations.filter(name__icontains=organization_name).filter(
            is_public=True
        )
    return organizations


def show_organization(user, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)
    is_admin = False
    permitted_users = None

    if user.is_authenticated:
        if user_has_admin_bookingpermission(user, organization):
            bookingpermissions = BookingPermission.objects.filter(
                organization=organization
            )
            permitted_users = (
                User.objects.filter(user_of_bookingpermission__in=bookingpermissions)
                .annotate(permission_status=F("user_of_bookingpermission__status"))
                .annotate(permission_role=F("user_of_bookingpermission__role"))
            ).order_by("id")
            is_admin = True

        elif user_has_normal_bookingpermission(user, organization):
            bookingpermissions = BookingPermission.objects.filter(
                organization=organization
            ).filter(status=BookingPermission.Status.CONFIRMED)
            permitted_users = (
                User.objects.filter(user_of_bookingpermission__in=bookingpermissions)
                .annotate(permission_status=F("user_of_bookingpermission__status"))
                .annotate(permission_role=F("user_of_bookingpermission__role"))
                .order_by("id")
            )

    if organization.is_public or permitted_users or is_admin:
        return organization, permitted_users, is_admin

    raise PermissionDenied


def create_organization(user, form):
    new_org = form.save(commit=False)
    if user.is_manager():
        new_org.status = BookingStatus.CONFIRMED
    new_org.save()

    new_org.organization_groups.set(form.cleaned_data["organization_groups"])
    default_groups = OrganizationGroup.objects.filter(default_group=True)
    new_org.organization_groups.add(*default_groups)

    bookingpermission = BookingPermission(
        user=user,
        organization=new_org,
        status=BookingPermission.Status.CONFIRMED,
        role=BookingPermission.Role.ADMIN,
    )
    bookingpermission.save()

    # Subscribe the given email to the newsletter via the Newsletter plugin API.
    if (
        form.cleaned_data["hde_newsletter"]
        or form.cleaned_data["hde_newsletter_for_actives"]
    ):
        newsletters = []
        if form.cleaned_data["hde_newsletter"]:
            newsletters.append(2)
        if form.cleaned_data["hde_newsletter_for_actives"]:
            newsletters.append(6)
        requests.post(
            settings.NEWSLETTER_API_URL,
            json={
                "email": form.cleaned_data["email"],
                "lists": newsletters,
            },
            timeout=15,
        )

    from re_sharing.organizations.mails import manager_new_organization_email

    manager_new_organization_email(new_org)
    return new_org


def update_organization(user, form, organization):
    if user_has_admin_bookingpermission(user, organization):
        organization = form.save(commit=False)
        organization.save()
        organization.organization_groups.set(form.cleaned_data["organization_groups"])
        return organization

    raise PermissionDenied


def user_has_bookingpermission(user, booking):
    if user.is_staff:
        return True
    return (
        BookingPermission.objects.filter(organization=booking.organization)
        .filter(user=user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .exists()
    )


def user_has_normal_bookingpermission(user, organization):
    return (
        BookingPermission.objects.filter(organization=organization)
        .filter(user=user)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .exists()
    )


def organizations_with_confirmed_bookingpermission(user):
    return Organization.objects.filter(
        organization_of_bookingpermission__user=user,
        organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED,
    ).distinct()


def user_has_admin_bookingpermission(user, organization):
    """Legacy function - Use selectors.user_has_admin_permission instead"""
    from .selectors import user_has_admin_permission

    return user_has_admin_permission(user, organization)


def manager_filter_organizations_list(status, group, manager=None):
    """
    Filter organizations based on status, group, and manager.
    If manager is provided and has organization_groups assigned, only organizations
    that are part of those groups will be returned.
    """
    organizations = Organization.objects.all()

    # Filter by manager's organization groups if manager is provided
    # and has organization groups
    if manager and manager.organization_groups.exists():
        organizations = organizations.filter(
            organization_groups__in=manager.organization_groups.all()
        ).distinct()

    if status != "all":
        organizations = organizations.filter(status__in=status)
    if group != "all":
        organizations = organizations.filter(organization_groups__slug=group)

    organizations = organizations.annotate(
        bookings_count=Count("booking_of_organization", distinct=True)
    ).prefetch_related()
    organizations = organizations.annotate(
        confirmed_users_count=Count(
            "organization_of_bookingpermission",
            filter=Q(
                organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED
            ),
            distinct=True,
        ),
    ).prefetch_related("organization_groups")

    return organizations.order_by(Lower("name"))


def manager_cancel_organization(user, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if organization.is_cancelable():
        with set_actor(user):
            organization.status = BookingStatus.CANCELLED
            organization.save()
        from re_sharing.organizations.mails import organization_cancellation_email

        organization_cancellation_email(organization)
        return organization

    raise InvalidOrganizationOperationError


def manager_confirm_organization(user, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if organization.is_confirmable():
        with set_actor(user):
            organization.status = BookingStatus.CONFIRMED
            organization.save()
        from re_sharing.organizations.mails import organization_confirmation_email

        organization_confirmation_email(organization)
        return organization

    raise InvalidOrganizationOperationError


def save_organizationmessage(organization, message, user):
    organization_message = OrganizationMessage(
        organization=organization,
        text=message,
        user=user,
    )
    organization_message.save()

    from re_sharing.organizations.mails import send_new_organization_message_email

    send_new_organization_message_email(organization_message)

    return organization_message


def create_organizationmessage(organization_slug, form, user):
    organization = get_object_or_404(Organization, slug=organization_slug)

    if not user_has_normal_bookingpermission(user, organization) and not user.is_staff:
        raise PermissionDenied

    if form.is_valid():
        message = form.cleaned_data["text"]
        return save_organizationmessage(organization, message, user)

    raise InvalidOrganizationOperationError


def request_booking_permission(user, organization):
    """Request booking permission for an organization - Business logic only"""
    from .selectors import get_user_permissions_for_organization

    # Check existing permissions via selector
    existing_permissions = get_user_permissions_for_organization(user, organization)

    if existing_permissions.exists():
        permission = existing_permissions.first()
        # Business logic validation
        if permission.status == BookingPermission.Status.PENDING:
            return (
                "You are already requested to become a member. Please wait patiently."
            )
        if permission.status == BookingPermission.Status.CONFIRMED:
            return "You are already member of this organization."
        if permission.status == BookingPermission.Status.REJECTED:
            return "You have already been rejected by this organization."

    # Business logic: Create new permission request
    BookingPermission.objects.create(
        user=user,
        organization=organization,
        status=BookingPermission.Status.PENDING,
        role=BookingPermission.Role.BOOKER,
    )
    return (
        "Successfully requested. "
        "You will be notified when your request is approved or denied."
    )


def add_user_to_organization(organization, email, role, admin_user):
    """Add a user to an organization with specified role - Business logic only"""
    from .selectors import get_user_by_email
    from .selectors import user_has_admin_permission

    # Business logic validation
    if not user_has_admin_permission(admin_user, organization):
        msg = "You are not allowed to add users to this organization."
        raise PermissionDenied(msg)

    if not email or not role:
        msg = "Email and role are required."
        raise ValueError(msg)

    # Get user via selector
    user = get_user_by_email(email)
    if not user:
        msg = f"No user found with email: {email}"
        raise ValueError(msg)

    # Business logic: Create or get permission
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

    # Business logic: Return appropriate message
    if created:
        return f"{user.email} was successfully added!"
    return f"{user.email} already has permissions."


def confirm_booking_permission(organization, user_slug, admin_user):
    """Confirm a booking permission request - Business logic only"""
    from .selectors import get_booking_permission
    from .selectors import user_has_admin_permission

    # Business logic validation
    if not user_has_admin_permission(admin_user, organization):
        msg = "You are not allowed to confirm this booking permission."
        raise PermissionDenied(msg)

    # Get permission via selector
    bookingpermission = get_booking_permission(organization, user_slug)

    if not bookingpermission:
        return "Booking permission does not exist."

    # Business logic validation
    if bookingpermission.status == BookingPermission.Status.CONFIRMED:
        return "Booking permission has already been confirmed."

    # Business logic: Update permission status
    bookingpermission.status = BookingPermission.Status.CONFIRMED
    bookingpermission.save()
    return "Booking permission has been confirmed."


def cancel_booking_permission(organization, user_slug, requesting_user):
    """Cancel a booking permission - Business logic only"""
    from .selectors import get_booking_permission
    from .selectors import user_has_admin_permission

    # Business logic validation: Check if user can cancel
    if not (
        requesting_user.slug == user_slug
        or user_has_admin_permission(requesting_user, organization)
    ):
        msg = "You are not allowed to cancel this booking permission."
        raise PermissionDenied(msg)

    # Get permission via selector
    bookingpermission = get_booking_permission(organization, user_slug)

    if not bookingpermission:
        return "Booking permission does not exist."

    # Business logic: Delete permission
    bookingpermission.delete()
    return "Booking permission has been cancelled."


def promote_user_to_admin(organization, user_slug, admin_user):
    """Promote a user to admin role - Business logic only"""
    from .selectors import get_booking_permission
    from .selectors import user_has_admin_permission

    # Business logic validation
    if not user_has_admin_permission(admin_user, organization):
        msg = "You are not allowed to promote users."
        raise PermissionDenied(msg)

    # Get permission via selector
    bookingpermission = get_booking_permission(organization, user_slug)

    if not bookingpermission:
        return "Booking permission does not exist."

    # Business logic validation
    if bookingpermission.status != BookingPermission.Status.CONFIRMED:
        return "Booking permission is not confirmed."

    # Business logic: Update role
    bookingpermission.role = BookingPermission.Role.ADMIN
    bookingpermission.save()
    return "User has been promoted to admin."


def demote_user_to_booker(organization, user_slug, admin_user):
    """Demote a user to booker role - Business logic only"""
    from .selectors import get_booking_permission
    from .selectors import user_has_admin_permission

    # Business logic validation
    if not user_has_admin_permission(admin_user, organization):
        msg = "You are not allowed to demote users."
        raise PermissionDenied(msg)

    # Get permission via selector
    bookingpermission = get_booking_permission(organization, user_slug)

    if not bookingpermission:
        return "Booking permission does not exist."

    # Business logic: Update role
    bookingpermission.role = BookingPermission.Role.BOOKER
    bookingpermission.save()
    return "User has been demoted to booker."
