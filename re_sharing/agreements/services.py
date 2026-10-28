"""Agreement lifecycle and SEPA mandates.

Collections, runs and returns live in ``services_collections``.
"""

from datetime import datetime
from datetime import time

from auditlog.context import set_actor
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from re_sharing.organizations.models import Organization

from .models import Agreement
from .models import Collection
from .models import SepaMandate
from .selectors import manager_can_manage_agreement
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
    existing = Agreement.objects.filter(
        organization=organization,
        kind=kind,
        status__in=[Agreement.Status.SUBMITTED, Agreement.Status.ACTIVE],
    ).first()
    if existing:
        msg = _("Your organization already has this agreement: %(agreement)s") % {
            "agreement": existing
        }
        raise AgreementError(msg)

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

    organization = agreement.organization
    group = agreement.kind.organization_group
    with transaction.atomic(), set_actor(user):
        agreement.end_date = agreement.end_date or end_date or timezone.localdate()
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

        agreement.collections_of_agreement.filter(
            status__in=[Collection.Status.PLANNED, Collection.Status.NOTIFIED],
            period_start__gt=agreement.end_date,
        ).update(status=Collection.Status.CANCELLED)

        _create_deposit_refund(agreement)
        transaction.on_commit(lambda: send_agreement_ended_email.enqueue(agreement.id))
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
