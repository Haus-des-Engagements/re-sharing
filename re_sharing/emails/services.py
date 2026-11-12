import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from re_sharing.emails.models import EmailLog

logger = logging.getLogger(__name__)

LOG_CONTEXT_ATTRIBUTE = "email_log_context"
UNDELIVERED_ERROR = "The delivering backend did not send the message."


def set_email_log_context(  # noqa: PLR0913
    message,
    *,
    email_type="",
    organization=None,
    booking=None,
    user=None,
    log_entry=None,
):
    """
    Tell the email log what a message is about.

    The values travel on the message and are read by the logging backend.
    With ``log_entry`` the backend records the outcome on that entry instead
    of creating a new one (a failed email that is sent again).
    """
    setattr(
        message,
        LOG_CONTEXT_ATTRIBUTE,
        {
            "email_type": str(email_type or ""),
            "organization": organization,
            "booking": booking,
            "user": user,
            "log_entry": log_entry,
        },
    )
    return message


def _attachment_name(attachment) -> str:
    filename = getattr(attachment, "filename", None)
    if filename is None and hasattr(attachment, "get_filename"):
        filename = attachment.get_filename()
    if filename is None and isinstance(attachment, tuple):
        filename = attachment[0]
    return str(filename or "")


def _html_alternative(message) -> str:
    for alternative in getattr(message, "alternatives", None) or []:
        content, mimetype = alternative[0], alternative[1]
        if mimetype == "text/html":
            return str(content)
    return ""


def record_email(message, *, error: str | None) -> EmailLog | None:
    """
    Store what was handed to the delivering backend and how it went.
    ``error`` is ``None`` for an accepted message. Never raises: a problem
    with the log must not stop an email.
    """
    try:
        # savepoint, so a failed write does not break the caller's transaction
        with transaction.atomic():
            return _write_entry(message, error)
    except Exception:
        logger.exception("Could not write the email log entry.")
        return None


def _write_entry(message, error) -> EmailLog:
    context = getattr(message, LOG_CONTEXT_ATTRIBUTE, None) or {}
    entry = context.get("log_entry")
    if entry is None:
        entry = EmailLog(
            email_type=context.get("email_type", ""),
            organization=context.get("organization"),
            booking=context.get("booking"),
            user=context.get("user"),
        )
    entry.from_email = message.from_email or ""
    entry.to = list(message.to)
    entry.cc = list(message.cc)
    entry.bcc = list(message.bcc)
    entry.subject = str(message.subject)
    if message.content_subtype == "html":
        entry.body_text = ""
        entry.body_html = str(message.body)
    else:
        entry.body_text = str(message.body)
        entry.body_html = _html_alternative(message)
    entry.attachment_names = [
        _attachment_name(attachment) for attachment in message.attachments
    ]
    entry.attempts += 1
    if error is None:
        entry.status = EmailLog.Status.SENT
        entry.error = ""
        entry.sent_at = timezone.now()
    else:
        entry.status = EmailLog.Status.FAILED
        entry.error = error
    entry.save()
    return entry


def enqueue_spaced(task, argument_lists) -> int:
    """
    Enqueue the task once per argument list, each start
    ``BULK_EMAIL_SEND_INTERVAL`` seconds after the previous one, so a bulk
    send stays below provider limits and other emails go out in between.
    An interval of 0, or a task backend that cannot delay, starts all at once.
    """
    interval = settings.BULK_EMAIL_SEND_INTERVAL
    can_delay = interval > 0 and task.get_backend().supports_defer
    start = timezone.now()
    count = 0
    for position, arguments in enumerate(argument_lists):
        scheduled = task
        if can_delay and position:
            scheduled = task.using(
                run_after=start + timedelta(seconds=position * interval)
            )
        scheduled.enqueue(*arguments)
        count += 1
    return count


def resend_emails(entries) -> int:
    """
    Send the entries again, spaced like a bulk send. A failed entry is
    retried on the same entry; a sent one is sent as a new email.
    Returns the number of scheduled emails.
    """
    from re_sharing.emails.tasks import resend_email

    return enqueue_spaced(
        resend_email, [(entry.pk, entry.is_failed) for entry in entries]
    )
