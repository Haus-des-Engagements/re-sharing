from django.db.models import F
from django.shortcuts import get_object_or_404

from roomsharing.users.models import User

from .models import BookingPermission
from .models import Organization


def filter_organizations(organization_name):
    organizations = Organization.objects.all()

    if organization_name:
        organizations = organizations.filter(name__icontains=organization_name)
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


def user_has_bookingpermission(user, booking):
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


def organizations_with_bookingpermission(user):
    return (
        Organization.objects.filter(organization_of_bookingpermission__user=user)
        .filter(
            organization_of_bookingpermission__status=BookingPermission.Status.CONFIRMED
        )
        .distinct()
    )


def user_has_admin_bookingpermission(user, organization):
    return (
        BookingPermission.objects.filter(user=user)
        .filter(organization=organization)
        .filter(status=BookingPermission.Status.CONFIRMED)
        .filter(role=BookingPermission.Role.ADMIN)
        .exists()
    )
