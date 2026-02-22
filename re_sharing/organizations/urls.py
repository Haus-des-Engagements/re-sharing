from django.urls import include
from django.urls import path

from .views import BookingPermissionView
from .views import EmailTemplateView
from .views import create_organization_view
from .views import create_organizationmessage_view
from .views import custom_organization_email_view
from .views import delete_organization_view
from .views import list_organizations_view
from .views import manager_cancel_organization_view
from .views import manager_confirm_organization_view
from .views import manager_list_organizations_view
from .views import manager_permanent_code_action_view
from .views import organization_permission_management_view
from .views import organization_permission_view
from .views import send_custom_organization_email_view
from .views import show_organization_messages_view
from .views import show_organization_view
from .views import update_organization_view

app_name = "organizations"
urlpatterns = [
    path("", list_organizations_view, name="list-organizations"),  # GET organizations
    path(
        "manage-organizations/",
        manager_list_organizations_view,
        name="manager-list-organizations",
    ),
    path(
        "manage-organizations/<slug:organization_slug>/cancel-organization/",
        manager_cancel_organization_view,
        name="manager-cancel-organization",
    ),
    path(
        "manage-organizations/<slug:organization_slug>/confirm-organization/",
        manager_confirm_organization_view,
        name="manager-confirm-organization",
    ),
    path(
        "manage-organizations/<slug:organization_slug>/permanent-code/",
        manager_permanent_code_action_view,
        name="manager-permanent-code-action",
    ),
    path(
        "<slug:organization>/edit/",
        update_organization_view,
        name="update-organization",
    ),
    path("new/", create_organization_view, name="create-organization"),
    path(
        "<slug:organization>/permissions/",
        organization_permission_view,
        name="organization-permissions",
    ),  # POST permission creation (request/add-user)
    path(
        "<slug:organization>/permissions/<slug:user>/",
        organization_permission_management_view,
        name="organization-permissions-manage",
    ),  # POST permission management (confirm/cancel/promote/demote)
    path(
        "<slug:organization>/delete-organization/",
        delete_organization_view,
        name="delete-organization",
    ),  # DELETE organization
    path(
        "<slug:slug>/create-message/",
        create_organizationmessage_view,
        name="create-organizationmessage",
    ),  # POST organization message
    path(
        "<slug:organization>/messages/",
        show_organization_messages_view,
        name="show-organization-messages",
    ),  # GET organization messages
    path("booking-permissions/", include(BookingPermissionView.get_urls())),
    path("email-templates/", include(EmailTemplateView.get_urls())),
    path(
        "custom-email/",
        custom_organization_email_view,
        name="custom-organization-email",
    ),  # GET custom email form
    path(
        "custom-email/send/",
        send_custom_organization_email_view,
        name="send-custom-organization-email",
    ),  # POST send custom email
    path(
        "<slug:organization>/", show_organization_view, name="show-organization"
    ),  # GET organization
]
