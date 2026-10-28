"""Emails of the agreements app, sent as background tasks.

Texts come from ``EmailTemplate`` rows like every other email. Contexts never
contain bank details: mandates appear only by their reference.
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.tasks import task

from re_sharing.organizations.mails import send_email_with_template
from re_sharing.organizations.models import EmailTemplate

EmailType = EmailTemplate.EmailTypeChoices


def organization_recipients(organization) -> list[str]:
    if organization.send_booking_emails_only_to_organization:
        return [organization.email]
    admins = list(organization.get_confirmed_admins().values_list("email", flat=True))
    return admins or [organization.email]


def _collection_context(collection) -> dict:
    return {
        "kind": collection.get_kind_display(),
        "period_start": collection.period_start,
        "period_end": collection.period_end,
        "due_date": collection.due_date,
        "amount": collection.amount,
        "reference": collection.reference,
        "invoice_number": collection.invoice_number,
        "invoice_amount": collection.invoice_amount,
    }


def agreement_context(agreement) -> dict:
    from .services_collections import first_period_collection_of

    mandate = agreement.active_mandate or agreement.open_mandate
    first_collection = first_period_collection_of(agreement)
    domain = Site.objects.get_current().domain
    return {
        "organization": agreement.organization,
        "agreement": agreement,
        "kind": agreement.kind,
        "domain": domain,
        "agreement_url": f"{domain}{agreement.get_absolute_url()}",
        "mandate_reference": mandate.reference if mandate else "",
        "creditor_id": settings.SEPA_CREDITOR_ID,
        "creditor_name": settings.SEPA_CREDITOR_NAME,
        "first_collection": (
            _collection_context(first_collection) if first_collection else None
        ),
    }


def _load_agreement(agreement_id):
    from .models import Agreement

    return Agreement.objects.select_related("organization", "kind").get(id=agreement_id)


def _send_to_organization(email_type, agreement_id, extra=None) -> dict:
    agreement = _load_agreement(agreement_id)
    context = agreement_context(agreement) | (extra or {})
    recipients = organization_recipients(agreement.organization)
    send_email_with_template(email_type, context, recipients)
    return {"agreement_id": agreement_id, "recipients": recipients}


@task(queue_name="email")
def send_agreement_application_emails(agreement_id: int) -> dict:
    """Confirmation to the organization and a notice to the managers."""
    result = _send_to_organization(
        EmailType.AGREEMENT_APPLICATION_RECEIVED, agreement_id
    )
    agreement = _load_agreement(agreement_id)
    send_email_with_template(
        EmailType.MANAGER_NEW_AGREEMENT,
        agreement_context(agreement),
        [settings.DEFAULT_MANAGER_EMAIL],
    )
    return result


@task(queue_name="email")
def send_agreement_approved_email(agreement_id: int) -> dict:
    return _send_to_organization(EmailType.AGREEMENT_APPROVED, agreement_id)


@task(queue_name="email")
def send_agreement_rejected_email(agreement_id: int) -> dict:
    return _send_to_organization(EmailType.AGREEMENT_REJECTED, agreement_id)


@task(queue_name="email")
def send_agreement_ended_email(agreement_id: int) -> dict:
    return _send_to_organization(EmailType.AGREEMENT_ENDED, agreement_id)


def _send_collection_email(email_type, collection_id) -> dict:
    from .models import Collection

    collection = Collection.objects.select_related("agreement", "mandate").get(
        id=collection_id
    )
    extra = {
        "collection": _collection_context(collection),
        "mandate_reference": collection.mandate.reference if collection.mandate else "",
    }
    return _send_to_organization(email_type, collection.agreement_id, extra)


@task(queue_name="email")
def send_pre_notification_email(collection_id: int) -> dict:
    return _send_collection_email(EmailType.AGREEMENT_PRE_NOTIFICATION, collection_id)


@task(queue_name="email")
def send_return_invoice_email(collection_id: int) -> dict:
    return _send_collection_email(EmailType.AGREEMENT_RETURN_INVOICE, collection_id)
