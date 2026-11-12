from datetime import date

from django.db.models import Q
from django.db.models import QuerySet

from re_sharing.emails.models import EmailLog


def get_email_logs(  # noqa: PLR0913
    *,
    search: str = "",
    status: str = "",
    email_type: str = "",
    organization=None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> QuerySet[EmailLog]:
    """
    Entries of the email log, newest first. ``search`` matches recipients
    (to, cc, bcc) and the subject; the date range is inclusive and refers to
    the day the entry was created.
    """
    entries = EmailLog.objects.select_related("organization", "booking", "user")
    if search:
        entries = entries.filter(
            Q(subject__icontains=search)
            | Q(to__icontains=search)
            | Q(cc__icontains=search)
            | Q(bcc__icontains=search)
        )
    if status:
        entries = entries.filter(status=status)
    if email_type:
        entries = entries.filter(email_type=email_type)
    if organization is not None:
        entries = entries.filter(organization=organization)
    if from_date is not None:
        entries = entries.filter(created__date__gte=from_date)
    if to_date is not None:
        entries = entries.filter(created__date__lte=to_date)
    return entries


def get_email_types() -> list[str]:
    """The types that occur in the log, for the filter."""
    return list(
        EmailLog.objects.exclude(email_type="")
        .order_by("email_type")
        .values_list("email_type", flat=True)
        .distinct()
    )
