from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.shortcuts import get_object_or_404

from roomsharing.users.models import User

from .models import BookingPermission
from .models import Organization


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

    if not organization.is_public and not permitted_users:
        raise PermissionDenied

    return organization, permitted_users, is_admin


def create_organization(user, form):
    new_org = form.save(commit=False)
    new_org.save()
    bookingpermission = BookingPermission(
        user=user,
        organization=new_org,
        status=BookingPermission.Status.CONFIRMED,
        role=BookingPermission.Role.ADMIN,
    )
    bookingpermission.save()
    return new_org


def update_organization(user, form, organization):
    if user_has_admin_bookingpermission(user, organization):
        organization = form.save(commit=False)
        organization.save()
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
    return (
        BookingPermission.objects.filter(user=user)
        .filter(organization=organization)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .filter(role=BookingPermission.Role.ADMIN)
        .exists()
    )
