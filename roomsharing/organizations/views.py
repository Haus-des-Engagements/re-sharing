from http import HTTPStatus

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from roomsharing.users.models import User

from .models import BookingPermission
from .models import Organization
from .selectors import user_has_admin_bookingpermission
from .selectors import user_has_normal_bookingpermission
from .services import filter_organizations


def list_organizations_view(request):
    organization_name = request.GET.get("organization_name")
    organizations = filter_organizations(organization_name)

    context = {"organizations": organizations}
    if request.headers.get("HX-Request"):
        return render(
            request, "organizations/partials/list_organizations.html", context
        )

    return render(request, "organizations/list_organizations.html", context)


@login_required
def show_organization_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    permitted = []
    is_admin = False

    if user_has_admin_bookingpermission(request.user, organization):
        bookingpermissions = BookingPermission.objects.filter(organization=organization)
        permitted = (
            User.objects.filter(user_of_bookingpermission__in=bookingpermissions)
            .annotate(permission_status=F("user_of_bookingpermission__status"))
            .annotate(permission_role=F("user_of_bookingpermission__role"))
        )
        is_admin = True

    elif user_has_normal_bookingpermission(request.user, organization):
        bookingpermissions = BookingPermission.objects.filter(organization=organization)
        permitted = User.objects.filter(
            user_of_bookingpermission__in=bookingpermissions
        ).values("first_name", "last_name", "email")

    return render(
        request,
        "organizations/show_organization.html",
        {"organization": organization, "permitted": permitted, "is_admin": is_admin},
    )


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
