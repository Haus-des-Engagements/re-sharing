from django.urls import path

from . import views

app_name = "agreements"
urlpatterns = [
    path(
        "organization/<slug:organization>/",
        views.organization_agreements_view,
        name="organization-agreements",
    ),
    path(
        "organization/<slug:organization>/apply/<slug:kind>/",
        views.apply_view,
        name="apply",
    ),
    path("<uuid:agreement>/", views.show_agreement_view, name="show-agreement"),
    path(
        "<uuid:agreement>/signed-document/",
        views.upload_signed_document_view,
        name="upload-signed-document",
    ),
    path(
        "<uuid:agreement>/contract.pdf",
        views.contract_document_view,
        name="contract-document",
    ),
    path(
        "<uuid:agreement>/mandate/new/",
        views.create_mandate_view,
        name="create-mandate",
    ),
    path("mandates/<uuid:mandate>/", views.show_mandate_view, name="show-mandate"),
    path(
        "mandates/<uuid:mandate>/mandate.pdf",
        views.mandate_document_view,
        name="mandate-document",
    ),
    path(
        "mandates/<uuid:mandate>/signed-document/",
        views.upload_signed_mandate_view,
        name="upload-signed-mandate",
    ),
    # Managers
    path(
        "manage/",
        views.manager_list_agreements_view,
        name="manager-list-agreements",
    ),
    path("manage/new/", views.manager_new_agreement_view, name="manager-new-agreement"),
    path(
        "manage/new/<slug:kind>/",
        views.manager_create_agreement_view,
        name="manager-create-agreement",
    ),
    path(
        "manage/<uuid:agreement>/edit/",
        views.manager_edit_agreement_view,
        name="manager-edit-agreement",
    ),
    path(
        "manage/<uuid:agreement>/delete/",
        views.manager_delete_agreement_view,
        name="manager-delete-agreement",
    ),
    path(
        "manage/<uuid:agreement>/approve/",
        views.manager_decide_agreement_view,
        {"decision": "approve"},
        name="manager-approve-agreement",
    ),
    path(
        "manage/<uuid:agreement>/reject/",
        views.manager_decide_agreement_view,
        {"decision": "reject"},
        name="manager-reject-agreement",
    ),
    path(
        "manage/<uuid:agreement>/end/",
        views.manager_end_agreement_view,
        name="manager-end-agreement",
    ),
    path(
        "manage/mandates/<uuid:mandate>/revoke/",
        views.manager_revoke_mandate_view,
        name="manager-revoke-mandate",
    ),
    path(
        "manage/collections/",
        views.manager_collections_view,
        name="manager-collections",
    ),
    path(
        "manage/collections/<uuid:collection>/paid/",
        views.manager_collection_action_view,
        {"action": "paid"},
        name="manager-collection-paid",
    ),
    path(
        "manage/collections/<uuid:collection>/cancel/",
        views.manager_collection_action_view,
        {"action": "cancel"},
        name="manager-collection-cancel",
    ),
    path(
        "manage/collections/<uuid:collection>/invoice/",
        views.manager_collection_action_view,
        {"action": "invoice"},
        name="manager-collection-invoice",
    ),
    path("manage/runs/", views.manager_runs_view, name="manager-runs"),
    path(
        "manage/runs/<uuid:run>/uploaded/",
        views.manager_run_action_view,
        {"action": "uploaded"},
        name="manager-run-uploaded",
    ),
    path(
        "manage/runs/<uuid:run>/delete/",
        views.manager_run_action_view,
        {"action": "delete"},
        name="manager-run-delete",
    ),
]
