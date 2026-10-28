"""Agreement lifecycle and SEPA mandates.

Collections, runs and returns live in ``services_collections``.
"""

from datetime import datetime
from datetime import time

from auditlog.context import set_actor
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import formats
from django.utils import timezone
from django.utils.translation import gettext as _

from re_sharing.organizations.models import Organization

from .models import Agreement
from .models import Collection
from .models import SepaMandate
from .selectors import manager_can_manage_agreement
from .selectors import manager_can_manage_kind
from .selectors import user_can_administer_agreement


class AgreementError(Exception):
    """An action is not possible in the agreement's current state."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


# =============================================================================
# References
# =============================================================================


def generate_mandate_reference(agreement: Agreement) -> str:
    """``<prefix>-<agreement id, six digits>-<n>``, skipping taken references."""
    prefix = settings.SEPA_MANDATE_PREFIX
    number = agreement.mandates_of_agreement.count() + 1
    while True:
        reference = f"{prefix}-{agreement.id:06d}-{number}"
        if not SepaMandate.objects.filter(reference=reference).exists():
            return reference
        number += 1


def generate_collection_reference(collection: Collection) -> str:
    """``<prefix>-C-<collection id, six digits>``, the SEPA end-to-end id."""
    return f"{settings.SEPA_MANDATE_PREFIX}-C-{collection.id:06d}"


# =============================================================================
# Mandates
# =============================================================================


def create_mandate(user, agreement: Agreement, form) -> SepaMandate:
    """Save bank data, with or without the signed mandate PDF."""
    if not user_can_administer_agreement(user, agreement):
        raise PermissionDenied
    if agreement.status not in (Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE):
        msg = _("Mandates can only be added to submitted or active agreements.")
        raise AgreementError(msg)
    if agreement.open_mandate is not None:
        msg = _(
            "This agreement already has a mandate. Ask a manager to revoke it before "
            "adding a new one."
        )
        raise AgreementError(msg)

    data = form.cleaned_data
    with transaction.atomic(), set_actor(user):
        mandate = SepaMandate(
            agreement=agreement,
            reference=generate_mandate_reference(agreement),
            account_holder=data["account_holder"],
            iban=data["iban"],
            bic=data.get("bic", ""),
            bank_name=data.get("bank_name", ""),
            signed_document=data.get("signed_document") or None,
            signed_on=data.get("signed_on"),
        )
        mandate.save()
    return mandate


def upload_signed_mandate(user, mandate: SepaMandate, form) -> SepaMandate:
    if not user_can_administer_agreement(user, mandate.agreement):
        raise PermissionDenied
    if mandate.revoked_on is not None:
        msg = _("A revoked mandate cannot be changed.")
        raise AgreementError(msg)

    with set_actor(user):
        mandate.signed_document = form.cleaned_data["signed_document"]
        mandate.signed_on = form.cleaned_data["signed_on"]
        mandate.save()
    return mandate


def revoke_mandate(user, mandate: SepaMandate, revoked_on) -> SepaMandate:
    if not manager_can_manage_agreement(user, mandate.agreement):
        raise PermissionDenied
    if mandate.revoked_on is not None:
        msg = _("This mandate is already revoked.")
        raise AgreementError(msg)

    with set_actor(user):
        mandate.revoked_on = revoked_on
        mandate.save()
    return mandate


# =============================================================================
# Agreement lifecycle
# =============================================================================


def _refuse_duplicate(organization, kind):
    existing = Agreement.objects.filter(
        organization=organization,
        kind=kind,
        status__in=[Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE],
    ).first()
    if existing:
        msg = _("The organization already has this agreement: %(agreement)s") % {
            "agreement": existing
        }
        raise AgreementError(msg)


def create_agreement(user, organization, kind, form) -> Agreement:
    """An organization's admin applies for a kind."""
    from .mails import send_agreement_application_emails
    from .selectors import is_confirmed_admin

    if not is_confirmed_admin(user, organization):
        raise PermissionDenied
    if organization.status != Organization.Status.CONFIRMED:
        msg = _(
            "Your organization must be confirmed before it can apply for an agreement."
        )
        raise AgreementError(msg)
    if not (kind.is_active and kind.accepting_applications):
        msg = _("Applications for this kind of agreement are closed.")
        raise AgreementError(msg)
    _refuse_duplicate(organization, kind)

    data = form.cleaned_data
    with transaction.atomic(), set_actor(user):
        agreement = Agreement.objects.create(
            organization=organization,
            kind=kind,
            amount=data["amount"],
            deposit_amount=data.get("deposit_amount"),
            start_date=data["start_date"],
            end_date=data.get("end_date"),
            contact_person_function=data.get("contact_person_function", ""),
            details=form.details(),
            signed_document=data.get("signed_document") or None,
            signed_on=data.get("signed_on"),
        )
        transaction.on_commit(
            lambda: send_agreement_application_emails.enqueue(agreement.id)
        )
    return agreement


def upload_signed_document(user, agreement: Agreement, form) -> Agreement:
    if not user_can_administer_agreement(user, agreement):
        raise PermissionDenied
    if agreement.status not in (Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE):
        msg = _("The contract of a closed agreement cannot be changed.")
        raise AgreementError(msg)

    with set_actor(user):
        agreement.signed_document = form.cleaned_data["signed_document"]
        agreement.signed_on = form.cleaned_data["signed_on"]
        agreement.save()
    return agreement


def _require_decision_rights(user, agreement):
    if not manager_can_manage_agreement(user, agreement):
        raise PermissionDenied
    if agreement.status != Agreement.Status.SUBMITTED:
        msg = _("Only submitted agreements can be decided.")
        raise AgreementError(msg)


def approve_agreement(user, agreement: Agreement, decided_at) -> Agreement:
    """Record the board's approval: group, code, deposit, first period, email."""
    from re_sharing.resources.services_permanent_code import (
        create_permanent_code_for_organization,
    )

    from .mails import send_agreement_approved_email
    from .services_collections import create_deposit_collection
    from .services_collections import create_first_period_collection

    _require_decision_rights(user, agreement)
    if not agreement.has_complete_signed_document:
        msg = _("The signed contract is missing.")
        raise AgreementError(msg)
    if agreement.active_mandate is None:
        if agreement.open_mandate is not None:
            msg = _("The signed SEPA mandate is missing.")
        else:
            msg = _("The SEPA mandate is missing.")
        raise AgreementError(msg)

    organization = agreement.organization
    kind = agreement.kind
    with transaction.atomic(), set_actor(user):
        agreement.status = Agreement.Status.ACTIVE
        agreement.decided_at = decided_at
        agreement.decided_by = user
        organization.organization_groups.add(kind.organization_group)
        accesses = list(kind.accesses.all())
        if accesses:
            agreement.permanent_code = create_permanent_code_for_organization(
                organization.slug,
                user,
                name=f"{kind.name} {organization.name}",
                accesses=accesses,
            )
        agreement.save()
        create_deposit_collection(agreement)
        create_first_period_collection(agreement, decided_at)
        transaction.on_commit(
            lambda: send_agreement_approved_email.enqueue(agreement.id)
        )
    return agreement


def reject_agreement(user, agreement: Agreement, decided_at) -> Agreement:
    from .mails import send_agreement_rejected_email

    _require_decision_rights(user, agreement)
    with transaction.atomic(), set_actor(user):
        agreement.status = Agreement.Status.REJECTED
        agreement.decided_at = decided_at
        agreement.decided_by = user
        agreement.save()
        transaction.on_commit(
            lambda: send_agreement_rejected_email.enqueue(agreement.id)
        )
    return agreement


def _end_of_day(day):
    end = datetime.combine(day, time.max)
    return timezone.make_aware(end, timezone.get_current_timezone())


def end_agreement(user, agreement: Agreement, end_date=None) -> Agreement:
    """End an active agreement. ``user`` is ``None`` for the daily command."""
    from .mails import send_agreement_ended_email

    if user is not None and not manager_can_manage_agreement(user, agreement):
        raise PermissionDenied
    if agreement.status != Agreement.Status.ACTIVE:
        msg = _("Only active agreements can be ended.")
        raise AgreementError(msg)
    end_date = end_date or agreement.end_date or timezone.localdate()

    organization = agreement.organization
    group = agreement.kind.organization_group
    with transaction.atomic(), set_actor(user):
        agreement.end_date = end_date
        agreement.status = Agreement.Status.ENDED
        agreement.save()

        still_granted = (
            Agreement.objects.filter(
                organization=organization,
                status=Agreement.Status.ACTIVE,
                kind__organization_group=group,
            )
            .exclude(id=agreement.id)
            .exists()
        )
        if not still_granted:
            organization.organization_groups.remove(group)

        code = agreement.permanent_code
        if code is not None:
            code_end = _end_of_day(agreement.end_date)
            if code.validity_end is None or code.validity_end > code_end:
                code.validity_end = code_end
                code.save(update_fields=["validity_end"])

        _drop_collections_after(agreement)

        _create_deposit_refund(agreement)
        transaction.on_commit(lambda: send_agreement_ended_email.enqueue(agreement.id))
    return agreement


def _require_end_not_before_start(agreement: Agreement, end_date):
    if end_date < agreement.start_date:
        msg = _("The end date cannot be before the start date.")
        raise AgreementError(msg)


def _drop_collections_after(agreement: Agreement) -> None:
    """Remove collections for periods after the end date. Planned ones are
    deleted so they come back if the date moves later; notified ones were
    announced to the organization and are cancelled instead."""
    later = agreement.collections_of_agreement.filter(
        period_start__gt=agreement.end_date
    )
    later.filter(status=Collection.Status.PLANNED).delete()
    later.filter(status=Collection.Status.NOTIFIED).update(
        status=Collection.Status.CANCELLED,
        status_note=_("The agreement ends on %(date)s.")
        % {"date": formats.date_format(agreement.end_date, "SHORT_DATE_FORMAT")},
    )


def schedule_agreement_end(user, agreement: Agreement, end_date) -> Agreement:
    """Save a future end date. The agreement stays active with its group and
    code; the daily command ends it after the date."""
    if not manager_can_manage_agreement(user, agreement):
        raise PermissionDenied
    if agreement.status != Agreement.Status.ACTIVE:
        msg = _("Only active agreements can be ended.")
        raise AgreementError(msg)
    if end_date <= timezone.localdate():
        msg = _("A scheduled end date must be in the future.")
        raise AgreementError(msg)
    _require_end_not_before_start(agreement, end_date)

    with transaction.atomic(), set_actor(user):
        agreement.end_date = end_date
        agreement.save()
        _drop_collections_after(agreement)
    return agreement


def _create_deposit_refund(agreement: Agreement) -> Collection | None:
    deposit = agreement.collections_of_agreement.filter(
        kind=Collection.Kind.DEPOSIT,
        status__in=[Collection.Status.COLLECTED, Collection.Status.PAID],
    ).first()
    if deposit is None:
        return None
    return Collection.objects.get_or_create(
        agreement=agreement,
        kind=Collection.Kind.DEPOSIT_REFUND,
        period_start=agreement.end_date,
        defaults={
            "period_end": agreement.end_date,
            "due_date": agreement.end_date,
            "amount": deposit.amount,
            "mandate": None,
        },
    )[0]


def end_expired_agreements(today) -> list[Agreement]:
    expired = Agreement.objects.filter(
        status=Agreement.Status.ACTIVE, end_date__lt=today
    ).select_related("kind", "organization", "permanent_code")
    return [end_agreement(None, agreement) for agreement in expired]


# =============================================================================
# Managers: create, edit, delete
# =============================================================================


def manager_create_agreement(user, organization, kind, form) -> Agreement:
    """Enter a paper application (submitted) or an existing agreement (active).

    An active agreement only gets the kind's group; no code, no collections and
    no email, since it already runs outside the system. The daily job bills
    periods due after it was created.
    """
    if not manager_can_manage_kind(user, kind):
        raise PermissionDenied
    if not kind.is_active:
        msg = _("This kind of agreement is inactive.")
        raise AgreementError(msg)
    if organization.status != Organization.Status.CONFIRMED:
        msg = _("Only confirmed organizations can have agreements.")
        raise AgreementError(msg)
    _refuse_duplicate(organization, kind)

    data = form.cleaned_data
    status = data["status"]
    is_active = status == Agreement.Status.ACTIVE
    with transaction.atomic(), set_actor(user):
        agreement = Agreement.objects.create(
            organization=organization,
            kind=kind,
            status=status,
            amount=data["amount"],
            deposit_amount=data.get("deposit_amount"),
            start_date=data["start_date"],
            end_date=data.get("end_date"),
            contact_person_function=data.get("contact_person_function", ""),
            details=form.details(),
            signed_document=data.get("signed_document") or None,
            signed_on=data.get("signed_on"),
            notes=data.get("notes", ""),
            decided_at=(data.get("decided_at") or timezone.localdate())
            if is_active
            else None,
            decided_by=user if is_active else None,
        )
        if is_active:
            organization.organization_groups.add(kind.organization_group)
    return agreement


def manager_update_agreement(user, agreement: Agreement, form) -> Agreement:
    """Change the data of an open agreement. Existing collections keep their
    amounts; a new amount applies to collections created afterwards."""
    if not manager_can_manage_agreement(user, agreement):
        raise PermissionDenied
    if agreement.status not in (Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE):
        msg = _("Closed agreements cannot be edited.")
        raise AgreementError(msg)

    data = form.cleaned_data
    previous_end = agreement.end_date
    with transaction.atomic(), set_actor(user):
        agreement.start_date = data["start_date"]
        agreement.amount = data["amount"]
        if "end_date" in form.fields:
            agreement.end_date = data.get("end_date")
        if "deposit_amount" in form.fields:
            agreement.deposit_amount = data.get("deposit_amount")
        agreement.contact_person_function = data.get("contact_person_function", "")
        agreement.notes = data.get("notes", "")
        agreement.details = {**agreement.details, **form.details()}
        agreement.save()
        if agreement.end_date and agreement.end_date != previous_end:
            _drop_collections_after(agreement)
    return agreement


def delete_agreement(user, agreement: Agreement) -> None:
    """Delete an untouched agreement with its mandates and stored documents."""
    from .selectors import agreement_can_be_deleted

    if not manager_can_manage_agreement(user, agreement):
        raise PermissionDenied
    if not agreement_can_be_deleted(agreement):
        msg = _(
            "Only submitted agreements without collections can be deleted. "
            "Reject or end it instead."
        )
        raise AgreementError(msg)

    mandates = list(agreement.mandates_of_agreement.all())
    files = [
        document
        for document in [agreement.signed_document]
        + [mandate.signed_document for mandate in mandates]
        if document
    ]
    stored = [(document.storage, document.name) for document in files]

    def remove_files():
        for storage, name in stored:
            storage.delete(name)

    with transaction.atomic(), set_actor(user):
        for mandate in mandates:
            mandate.delete()
        agreement.delete()
        transaction.on_commit(remove_files)
