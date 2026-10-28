from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from re_sharing.organizations.models import Organization
from re_sharing.providers.decorators import manager_required

from . import selectors
from . import services
from . import services_collections
from .forms import BuildRunForm
from .forms import CollectionNoteForm
from .forms import DecisionForm
from .forms import EndAgreementForm
from .forms import MandateForm
from .forms import RevokeMandateForm
from .forms import SignedDocumentForm
from .forms import application_form_class
from .forms import detail_items
from .models import Agreement
from .models import AgreementKind
from .models import Collection
from .models import CollectionRun
from .models import SepaMandate
from .models import UnmatchedReturn
from .services import AgreementError


def _refused(request, error: AgreementError):
    messages.error(request, error.message)


# =============================================================================
# Organization users
# =============================================================================


@login_required
def organization_agreements_view(request, organization):
    organization = get_object_or_404(Organization, slug=organization)
    if not selectors.user_can_view_organization_agreements(request.user, organization):
        raise PermissionDenied

    is_admin = selectors.is_confirmed_admin(request.user, organization)
    can_apply = is_admin and organization.status == Organization.Status.CONFIRMED
    context = {
        "organization": organization,
        "agreements": selectors.organization_agreements(organization),
        "open_kinds": (
            selectors.open_kinds_for_organization(organization) if can_apply else []
        ),
        "is_admin": is_admin,
    }
    return render(request, "agreements/organization_agreements.html", context)


@login_required
def apply_view(request, organization, kind):
    organization = get_object_or_404(Organization, slug=organization)
    kind = get_object_or_404(AgreementKind, slug=kind)
    if not selectors.is_confirmed_admin(request.user, organization):
        raise PermissionDenied
    if organization.status != Organization.Status.CONFIRMED:
        messages.error(
            request,
            _(
                "Your organization must be confirmed before it can apply for an "
                "agreement."
            ),
        )
        return redirect("organizations:show-organization", organization.slug)
    if not (kind.is_active and kind.accepting_applications):
        raise PermissionDenied

    form_class = application_form_class(kind)
    form = form_class(kind=kind)
    if request.method == "POST":
        form = form_class(data=request.POST, files=request.FILES, kind=kind)
        if form.is_valid():
            try:
                agreement = services.create_agreement(
                    request.user, organization, kind, form
                )
            except AgreementError as error:
                form.add_error(None, error.message)
            else:
                messages.success(request, _("Your application was submitted."))
                return redirect(agreement.get_absolute_url())

    context = {"organization": organization, "kind": kind, "form": form}
    return render(request, "agreements/apply.html", context)


def _agreement_for(request, agreement_uuid) -> Agreement:
    agreement = get_object_or_404(
        Agreement.objects.select_related("organization", "kind"), uuid=agreement_uuid
    )
    if not selectors.user_can_view_agreement(request.user, agreement):
        raise PermissionDenied
    return agreement


@login_required
def show_agreement_view(request, agreement):
    agreement = _agreement_for(request, agreement)
    is_manager = selectors.manager_can_manage_agreement(request.user, agreement)
    can_administer = selectors.user_can_administer_agreement(request.user, agreement)
    context = {
        "agreement": agreement,
        "details": detail_items(agreement),
        "collections": agreement.collections_of_agreement.all(),
        "mandates": agreement.mandates_of_agreement.all(),
        "open_mandate": agreement.open_mandate,
        "is_manager": is_manager,
        "can_administer": can_administer,
        "upload_form": SignedDocumentForm(),
        "decision_form": DecisionForm(initial={"decided_at": timezone.localdate()}),
        "end_form": EndAgreementForm(),
        "is_open": agreement.status
        in (Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE),
    }
    return render(request, "agreements/show_agreement.html", context)


@login_required
@require_POST
def upload_signed_document_view(request, agreement):
    agreement = _agreement_for(request, agreement)
    form = SignedDocumentForm(data=request.POST, files=request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(agreement.get_absolute_url())
    try:
        services.upload_signed_document(request.user, agreement, form)
    except AgreementError as error:
        _refused(request, error)
    else:
        messages.success(request, _("The signed contract was uploaded."))
    return redirect(agreement.get_absolute_url())


@login_required
def create_mandate_view(request, agreement):
    agreement = _agreement_for(request, agreement)
    if not selectors.user_can_administer_agreement(request.user, agreement):
        raise PermissionDenied
    if agreement.open_mandate is not None:
        return redirect(agreement.open_mandate.get_absolute_url())

    form = MandateForm()
    if request.method == "POST":
        form = MandateForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            try:
                mandate = services.create_mandate(request.user, agreement, form)
            except AgreementError as error:
                form.add_error(None, error.message)
            else:
                messages.success(request, _("The mandate was saved."))
                return redirect(mandate.get_absolute_url())

    context = {"agreement": agreement, "form": form}
    return render(request, "agreements/create_mandate.html", context)


def _mandate_for(request, mandate_uuid) -> SepaMandate:
    mandate = get_object_or_404(
        SepaMandate.objects.select_related(
            "agreement__organization", "agreement__kind"
        ),
        uuid=mandate_uuid,
    )
    if not selectors.user_can_administer_agreement(request.user, mandate.agreement):
        raise PermissionDenied
    return mandate


@login_required
def show_mandate_view(request, mandate):
    mandate = _mandate_for(request, mandate)
    is_manager = selectors.manager_can_manage_agreement(request.user, mandate.agreement)
    context = {
        "mandate": mandate,
        "agreement": mandate.agreement,
        "iban": mandate.iban if is_manager else mandate.masked_iban,
        "is_manager": is_manager,
        "upload_form": SignedDocumentForm(),
        "revoke_form": RevokeMandateForm(initial={"revoked_on": timezone.localdate()}),
        "mandate_form_url": settings.SEPA_MANDATE_FORM_URL,
    }
    return render(request, "agreements/show_mandate.html", context)


@login_required
@require_POST
def upload_signed_mandate_view(request, mandate):
    mandate = _mandate_for(request, mandate)
    form = SignedDocumentForm(data=request.POST, files=request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect(mandate.get_absolute_url())
    try:
        services.upload_signed_mandate(request.user, mandate, form)
    except AgreementError as error:
        _refused(request, error)
    else:
        messages.success(request, _("The signed mandate was uploaded."))
    return redirect(mandate.get_absolute_url())


# =============================================================================
# Managers
# =============================================================================


@manager_required
def manager_list_agreements_view(request):
    status = request.GET.get("status") or None
    kind = request.GET.get("kind") or None
    context = {
        "agreements": selectors.manager_agreements(
            request.user, status=status, kind=kind
        ),
        "kinds": selectors.manager_kinds(request.user),
        "statuses": Agreement.Status.choices,
        "selected_status": status,
        "selected_kind": kind,
        "submitted_count": selectors.manager_submitted_agreements_count(request.user),
    }
    return render(request, "agreements/manager_list_agreements.html", context)


def _manager_action(request, agreement_uuid, action):
    agreement = get_object_or_404(Agreement, uuid=agreement_uuid)
    try:
        action(agreement)
    except AgreementError as error:
        _refused(request, error)
    return redirect(agreement.get_absolute_url())


@manager_required
@require_POST
def manager_decide_agreement_view(request, agreement, decision):
    form = DecisionForm(data=request.POST)
    if not form.is_valid():
        messages.error(request, _("Enter the date of the board decision."))
        return redirect("agreements:show-agreement", agreement)
    service = {
        "approve": services.approve_agreement,
        "reject": services.reject_agreement,
    }[decision]

    def decide(item):
        service(request.user, item, form.cleaned_data["decided_at"])
        messages.success(request, _("The decision was recorded."))

    return _manager_action(request, agreement, decide)


@manager_required
@require_POST
def manager_end_agreement_view(request, agreement):
    form = EndAgreementForm(data=request.POST)
    end_date = form.cleaned_data["end_date"] if form.is_valid() else None

    def end(item):
        services.end_agreement(request.user, item, end_date)
        messages.success(request, _("The agreement was ended."))

    return _manager_action(request, agreement, end)


@manager_required
@require_POST
def manager_revoke_mandate_view(request, mandate):
    mandate = get_object_or_404(SepaMandate, uuid=mandate)
    form = RevokeMandateForm(data=request.POST)
    if form.is_valid():
        try:
            services.revoke_mandate(
                request.user, mandate, form.cleaned_data["revoked_on"]
            )
        except AgreementError as error:
            _refused(request, error)
        else:
            messages.success(request, _("The mandate was revoked."))
    return redirect(mandate.get_absolute_url())


@manager_required
def manager_collections_view(request):
    status = request.GET.get("status") or None
    kind = request.GET.get("kind") or None
    agreement_kind = request.GET.get("agreement_kind") or None
    today = timezone.localdate()
    context = {
        "collections": selectors.manager_collections(
            request.user, status=status, kind=kind, agreement_kind=agreement_kind
        ),
        "attention": selectors.manager_attention_collections(request.user, today=today),
        "runs_not_uploaded": selectors.runs_not_uploaded(),
        "unmatched_returns": UnmatchedReturn.objects.filter(resolved=False),
        "statuses": Collection.Status.choices,
        "kinds": Collection.Kind.choices,
        "agreement_kinds": selectors.manager_kinds(request.user),
        "selected": {
            "status": status,
            "kind": kind,
            "agreement_kind": agreement_kind,
        },
        "note_form": CollectionNoteForm(),
    }
    return render(request, "agreements/manager_collections.html", context)


@manager_required
@require_POST
def manager_collection_action_view(request, collection, action):
    collection = get_object_or_404(Collection, uuid=collection)
    note = request.POST.get("note", "")
    try:
        if action == "paid":
            services_collections.mark_collection_paid(request.user, collection, note)
        elif action == "cancel":
            services_collections.cancel_collection(request.user, collection, note)
        else:
            services_collections.invoice_returned_collection(request.user, collection)
    except AgreementError as error:
        _refused(request, error)
    else:
        messages.success(request, _("The collection was updated."))
    return redirect("agreements:manager-collections")


@manager_required
def manager_runs_view(request):
    form = BuildRunForm(initial={"collection_date": timezone.localdate()})
    if request.method == "POST":
        form = BuildRunForm(data=request.POST)
        if form.is_valid():
            try:
                services_collections.build_collection_run(
                    request.user, form.cleaned_data["collection_date"]
                )
            except AgreementError as error:
                _refused(request, error)
            else:
                messages.success(request, _("The SEPA file was created."))
                return redirect("agreements:manager-runs")

    context = {"runs": selectors.manager_runs(), "form": form}
    return render(request, "agreements/manager_runs.html", context)


@manager_required
@require_POST
def manager_run_action_view(request, run, action):
    run = get_object_or_404(CollectionRun, uuid=run)
    try:
        if action == "uploaded":
            services_collections.mark_run_uploaded(request.user, run)
            messages.success(request, _("The run is marked as uploaded."))
        else:
            services_collections.delete_collection_run(request.user, run)
            messages.success(request, _("The run was deleted."))
    except AgreementError as error:
        _refused(request, error)
    return redirect("agreements:manager-runs")
