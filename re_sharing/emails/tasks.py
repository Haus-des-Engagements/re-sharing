import logging

from django.core.mail import EmailMessage
from django.core.mail import EmailMultiAlternatives
from django.tasks import task

from re_sharing.emails.models import EmailLog
from re_sharing.emails.services import set_email_log_context

logger = logging.getLogger(__name__)


def build_message_from_entry(entry: EmailLog) -> EmailMessage:
    """The stored email again, without its attachments (they are not stored)."""
    addresses = {
        "from_email": entry.from_email or None,
        "to": entry.to,
        "cc": entry.cc,
        "bcc": entry.bcc,
    }
    if entry.body_html and not entry.body_text:
        message = EmailMessage(subject=entry.subject, body=entry.body_html, **addresses)
        message.content_subtype = "html"
        return message
    message = EmailMultiAlternatives(
        subject=entry.subject, body=entry.body_text, **addresses
    )
    if entry.body_html:
        message.attach_alternative(entry.body_html, "text/html")
    return message


@task(queue_name="email")
def resend_email(email_log_id: int, retry: bool) -> dict:  # noqa: FBT001
    """
    Send a logged email again.

    ``retry`` is set for an entry that had failed: the outcome is recorded on
    that entry, and nothing is sent if it became sent in the meantime. Without
    it the email goes out as a new email with an entry of its own.
    """
    entry = EmailLog.objects.select_related("organization", "booking", "user").get(
        pk=email_log_id
    )
    if retry and not entry.is_failed:
        return {"sent": False, "reason": "already_sent"}

    message = build_message_from_entry(entry)
    set_email_log_context(
        message,
        email_type=entry.email_type,
        organization=entry.organization,
        booking=entry.booking,
        user=entry.user,
        log_entry=entry if retry else None,
    )
    try:
        message.send(fail_silently=False)
    except Exception:
        logger.exception("Failed to send email log entry %s again", entry.pk)
        return {"sent": False, "reason": "smtp_error"}
    return {"sent": True, "email_log_id": entry.pk}
