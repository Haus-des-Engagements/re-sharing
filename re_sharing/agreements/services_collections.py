"""Collections: billing periods, pre-notification, SEPA runs, returns, invoices.

Fee periods are calendar months or calendar years. A partial first period is
prorated from the agreement's start date and created at approval; the daily
command only creates full periods (design D5).
"""

import calendar
import logging
import re
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from decimal import ROUND_HALF_UP
from decimal import Decimal
from decimal import InvalidOperation

from auditlog.context import set_actor
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from sepaxml import SepaDD

from re_sharing.utils import buchhaltungsbutler
from re_sharing.utils.buchhaltungsbutler import BuchhaltungsButlerError

from .models import RETURN_INVOICE_DUE_DAYS
from .models import Agreement
from .models import AgreementKind
from .models import Collection
from .models import CollectionRun
from .models import SyncState
from .models import UnmatchedReturn
from .selectors import agreement_has_active_mandate
from .selectors import manager_can_manage_agreement
from .services import AgreementError
from .services import generate_collection_reference

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
MONTHS_PER_YEAR = 12
SEPA_SCHEMA = "pain.008.001.08"
RETURNS_SYNC_KEY = "collection_returns"
# Words that mark a negative transaction as a returned direct debit when no
# reference matches. To be confirmed with the first real return.
RETURN_KEYWORDS = ("RUECKLASTSCHRIFT", "RÜCKLASTSCHRIFT", "RETOURE", "LASTSCHRIFT")
PAID_PAYMENT_STATUSES = {"paid", "bezahlt"}


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    due_date: date


def _money(value) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _last_day_of_month(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _first_of_next_month(day: date) -> date:
    return _last_day_of_month(day) + timedelta(days=1)


# =============================================================================
# Periods
# =============================================================================


def regular_due_date(kind: AgreementKind, period_start: date) -> date:
    """Yearly: the kind's fixed date in that year. Monthly: the collection day."""
    if kind.is_yearly:
        return date(period_start.year, kind.collection_month, kind.collection_day)
    return period_start.replace(day=kind.collection_day)


def _full_period(kind: AgreementKind, start: date) -> Period:
    end = date(start.year, 12, 31) if kind.is_yearly else _last_day_of_month(start)
    return Period(start=start, end=end, due_date=regular_due_date(kind, start))


def first_full_period_start(agreement: Agreement) -> date:
    start = agreement.start_date
    if agreement.kind.is_yearly:
        return (
            start if (start.month, start.day) == (1, 1) else date(start.year + 1, 1, 1)
        )
    return start if start.day == 1 else _first_of_next_month(start)


def next_billing_periods(agreement: Agreement, until: date) -> list[Period]:
    """Full periods from the first full one whose due date is up to ``until``,
    never starting after the end date."""
    kind = agreement.kind
    periods = []
    start = first_full_period_start(agreement)
    while True:
        period = _full_period(kind, start)
        if period.due_date > until:
            return periods
        if agreement.end_date and period.start > agreement.end_date:
            return periods
        periods.append(period)
        start = period.end + timedelta(days=1)


@dataclass(frozen=True)
class FirstPeriod:
    start: date
    end: date
    amount: Decimal


def partial_first_period(agreement: Agreement) -> FirstPeriod | None:
    """The prorated rest of the period the start date falls into, if any.

    Yearly: one twelfth per full month after the start month. Monthly: by day,
    start date and last day both included. Always from the start date.
    """
    start = agreement.start_date
    if agreement.kind.is_yearly:
        if (start.month, start.day) == (1, 1):
            return None
        months = MONTHS_PER_YEAR - start.month
        if months == 0:
            return None
        return FirstPeriod(
            start=_first_of_next_month(start),
            end=date(start.year, 12, 31),
            amount=_money(agreement.amount * months / MONTHS_PER_YEAR),
        )

    if start.day == 1:
        return None
    days_in_month = calendar.monthrange(start.year, start.month)[1]
    days = days_in_month - start.day + 1
    return FirstPeriod(
        start=start,
        end=_last_day_of_month(start),
        amount=_money(agreement.amount * days / days_in_month),
    )


def _new_collection(agreement, **fields) -> Collection:
    collection = Collection.objects.create(agreement=agreement, **fields)
    if fields.get("kind") != Collection.Kind.DEPOSIT_REFUND:
        collection.reference = generate_collection_reference(collection)
        collection.save(update_fields=["reference"])
    return collection


def create_first_period_collection(
    agreement: Agreement, decided_at: date
) -> Collection | None:
    """Created at approval as notified: the approval email announces it."""
    first = partial_first_period(agreement)
    if first is None:
        return None
    earliest = decided_at + timedelta(days=settings.PRE_NOTIFICATION_DAYS)
    due_date = max(regular_due_date(agreement.kind, first.start), earliest)
    return _new_collection(
        agreement,
        kind=Collection.Kind.FEE,
        period_start=first.start,
        period_end=first.end,
        due_date=due_date,
        amount=first.amount,
        mandate=agreement.active_mandate,
        status=Collection.Status.NOTIFIED,
        notified_at=timezone.now(),
    )


def first_period_collection_of(agreement: Agreement) -> Collection | None:
    first = partial_first_period(agreement)
    if first is None:
        return None
    return agreement.collections_of_agreement.filter(
        kind=Collection.Kind.FEE, period_start=first.start
    ).first()


def create_deposit_collection(agreement: Agreement) -> Collection | None:
    if not agreement.kind.requires_deposit or not agreement.deposit_amount:
        return None
    return _new_collection(
        agreement,
        kind=Collection.Kind.DEPOSIT,
        period_start=agreement.start_date,
        period_end=agreement.start_date,
        due_date=agreement.start_date,
        amount=agreement.deposit_amount,
        mandate=agreement.active_mandate,
    )


def create_due_collections(today: date) -> list[Collection]:
    """Fee collections for full periods due within the lookahead.

    Periods due before the agreement was created are skipped: agreements
    entered in the admin were paid on paper until then. Idempotent; a
    cancelled period is never recreated.
    """
    until = today + timedelta(days=settings.COLLECTION_LOOKAHEAD_DAYS)
    created = []
    agreements = Agreement.objects.filter(
        status=Agreement.Status.ACTIVE, kind__is_active=True
    ).select_related("kind")
    for agreement in agreements:
        for period in next_billing_periods(agreement, until):
            if period.due_date < agreement.created.date():
                continue
            exists = agreement.collections_of_agreement.filter(
                kind=Collection.Kind.FEE, period_start=period.start
            ).exists()
            if exists:
                continue
            created.append(
                _new_collection(
                    agreement,
                    kind=Collection.Kind.FEE,
                    period_start=period.start,
                    period_end=period.end,
                    due_date=period.due_date,
                    amount=agreement.amount,
                    mandate=agreement.active_mandate,
                )
            )
    return created


def notify_due_collections(today: date) -> list[Collection]:
    from .mails import send_pre_notification_email

    limit = today + timedelta(days=settings.PRE_NOTIFICATION_DAYS)
    due = Collection.objects.filter(
        status=Collection.Status.PLANNED,
        due_date__lte=limit,
        kind__in=[Collection.Kind.FEE, Collection.Kind.DEPOSIT],
    ).select_related("agreement__kind")
    notified = []
    for collection in due:
        collection.status = Collection.Status.NOTIFIED
        collection.notified_at = timezone.now()
        # The pre-notification names the mandate that will be used.
        collection.mandate = collection.agreement.active_mandate or collection.mandate
        collection.save(update_fields=["status", "notified_at", "mandate"])
        mode = collection.agreement.kind.notification_mode
        if mode == AgreementKind.NotificationMode.EACH_COLLECTION:
            transaction.on_commit(
                lambda cid=collection.id: send_pre_notification_email.enqueue(cid)
            )
        notified.append(collection)
    return notified


# =============================================================================
# Runs
# =============================================================================


def _require_manager(user, agreement=None):
    if not user.is_authenticated or not user.is_manager():
        raise PermissionDenied
    if agreement is not None and not manager_can_manage_agreement(user, agreement):
        raise PermissionDenied


def collections_for_run(collection_date: date):
    """Notified collections due by the date whose agreement has an active
    mandate now. The mandate is taken at build time, so a mandate added or
    replaced after the collection was created is used."""
    return (
        Collection.objects.filter(
            status=Collection.Status.NOTIFIED,
            due_date__lte=collection_date,
            kind__in=[Collection.Kind.FEE, Collection.Kind.DEPOSIT],
        )
        .filter(agreement_has_active_mandate())
        .select_related("agreement__kind", "agreement__organization")
        .prefetch_related("agreement__mandates_of_agreement")
    )


def _remittance(collection: Collection) -> str:
    kind = collection.agreement.kind.name
    if collection.kind == Collection.Kind.DEPOSIT:
        return f"{kind} Kaution {collection.reference}"
    period = f"{collection.period_start:%d.%m.%Y}-{collection.period_end:%d.%m.%Y}"
    return f"{kind} {period} {collection.reference}"


def build_sepa_xml(collections, collection_date: date) -> bytes:
    sepa = SepaDD(
        {
            "name": settings.SEPA_CREDITOR_NAME,
            "IBAN": settings.SEPA_CREDITOR_IBAN,
            "BIC": settings.SEPA_CREDITOR_BIC,
            "batch": False,
            "creditor_id": settings.SEPA_CREDITOR_ID,
            "currency": "EUR",
            "instrument": "CORE",
        },
        schema=SEPA_SCHEMA,
        clean=True,
    )
    for collection in collections:
        mandate = collection.mandate
        payment = {
            "name": mandate.account_holder,
            "IBAN": mandate.iban,
            "amount": int((collection.amount * 100).to_integral_value()),
            "type": "RCUR",
            "collection_date": collection_date,
            "mandate_id": mandate.reference,
            "mandate_date": mandate.signed_on,
            "description": _remittance(collection),
            "endtoend_id": collection.reference,
        }
        if mandate.bic:
            payment["BIC"] = mandate.bic
        sepa.add_payment(payment)
    return sepa.export(validate=True)


def build_collection_run(user, collection_date: date) -> CollectionRun:
    _require_manager(user)
    collections = list(collections_for_run(collection_date))
    if not collections:
        msg = _("No notified collections are due by this date.")
        raise AgreementError(msg)

    for collection in collections:
        collection.mandate = collection.agreement.active_mandate

    with transaction.atomic(), set_actor(user):
        Collection.objects.bulk_update(collections, ["mandate"])
        run = CollectionRun.objects.create(
            collection_date=collection_date,
            created_by=user,
            count=len(collections),
            total_amount=sum((c.amount for c in collections), Decimal(0)),
        )
        xml = build_sepa_xml(collections, collection_date)
        run.xml_file.save(f"sepa_{collection_date:%Y%m%d}.xml", ContentFile(xml))
        Collection.objects.filter(id__in=[c.id for c in collections]).update(
            status=Collection.Status.SUBMITTED, run=run
        )
    return run


def mark_run_uploaded(user, run: CollectionRun) -> CollectionRun:
    _require_manager(user)
    if run.uploaded_at:
        msg = _("This run is already marked as uploaded.")
        raise AgreementError(msg)
    with set_actor(user):
        run.uploaded_at = timezone.now()
        run.uploaded_by = user
        run.save(update_fields=["uploaded_at", "uploaded_by"])
    return run


def delete_collection_run(user, run: CollectionRun) -> None:
    _require_manager(user)
    if run.uploaded_at:
        msg = _("An uploaded run cannot be deleted.")
        raise AgreementError(msg)
    with transaction.atomic(), set_actor(user):
        run.collections_of_run.update(status=Collection.Status.NOTIFIED, run=None)
        run.xml_file.delete(save=False)
        run.delete()


def mark_collected(today: date) -> int:
    cutoff = today - timedelta(days=settings.COLLECTION_RETURN_WINDOW_DAYS)
    collections = Collection.objects.filter(
        status=Collection.Status.SUBMITTED,
        run__uploaded_at__isnull=False,
        run__collection_date__lt=cutoff,
    ).select_related("run")
    count = 0
    for collection in collections:
        collection.status = Collection.Status.COLLECTED
        collection.collected_at = collection.run.collection_date
        collection.save(update_fields=["status", "collected_at"])
        count += 1
    return count


# =============================================================================
# Returns
# =============================================================================


def _reference_in(reference: str, text: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(reference)}(?![\w-])", text) is not None


def _transaction_text(row: dict) -> str:
    parts = [
        row.get(key) or "" for key in ("purpose", "booking_text", "payment_reference")
    ]
    return " ".join(str(part) for part in parts if part)


def _amount_of(row: dict) -> Decimal | None:
    try:
        return Decimal(str(row.get("amount")).replace(",", "."))
    except (InvalidOperation, TypeError):
        return None


def _parse_booked_on(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _match_return(text: str, amount: Decimal, candidates) -> Collection | None:
    for collection in candidates:
        if collection.reference and _reference_in(collection.reference, text):
            return collection
    matches = [
        collection
        for collection in candidates
        if collection.mandate
        and collection.amount == abs(amount)
        and _reference_in(collection.mandate.reference, text)
    ]
    if matches:
        return max(matches, key=lambda collection: collection.due_date)
    return None


def _looks_like_return(text: str) -> bool:
    upper = text.upper()
    prefix = f"{settings.SEPA_MANDATE_PREFIX}-"
    creditor = settings.SEPA_CREDITOR_ID
    return (
        any(word in upper for word in RETURN_KEYWORDS)
        or prefix in text
        or bool(creditor and creditor in text)
    )


def detect_returns(now: datetime | None = None) -> dict:
    """Scan bank transactions since the last successful run for returns."""
    now = now or timezone.now()
    state = SyncState.objects.filter(key=RETURNS_SYNC_KEY).first()
    since = state.synced_at.strftime("%Y-%m-%d %H:%M:%S") if state else None
    try:
        rows = buchhaltungsbutler.get_transactions(date_since_last_modified=since)
    except BuchhaltungsButlerError:
        logger.exception("Could not read bank transactions for return detection")
        return {"status": "error"}

    candidates = list(
        Collection.objects.filter(
            status__in=[Collection.Status.SUBMITTED, Collection.Status.COLLECTED]
        ).select_related("mandate")
    )
    returned, unmatched = 0, 0
    for row in rows:
        amount = _amount_of(row)
        if amount is None or amount >= 0:
            continue
        text = _transaction_text(row)
        collection = _match_return(text, amount, candidates)
        if collection:
            collection.status = Collection.Status.RETURNED
            collection.returned_at = now
            collection.return_text = text
            collection.save(update_fields=["status", "returned_at", "return_text"])
            candidates.remove(collection)
            returned += 1
        elif _looks_like_return(text):
            _, created = UnmatchedReturn.objects.get_or_create(
                transaction_id=str(row.get("id") or row.get("transaction_id") or text),
                defaults={
                    "amount": amount,
                    "text": text,
                    "booked_on": _parse_booked_on(row.get("date")),
                },
            )
            unmatched += int(created)

    SyncState.objects.update_or_create(
        key=RETURNS_SYNC_KEY, defaults={"synced_at": now}
    )
    return {"status": "success", "returned": returned, "unmatched": unmatched}


# =============================================================================
# Return invoices and manual settlement
# =============================================================================


def build_return_invoice_payload(collection: Collection) -> dict:
    organization = collection.agreement.organization
    fee = settings.SEPA_RETURN_FEE
    item_names = [f"Rücklastschrift {_remittance(collection)}"]
    item_prices = [f"{collection.amount:.2f}"]
    if fee:
        item_names.append("Gebühr für die Rücklastschrift")
        item_prices.append(f"{fee:.2f}")
    count = len(item_names)
    return {
        "type": "invoice",
        "show_prices_type": "gross",
        "company_name": organization.name,
        "date": timezone.now().strftime("%Y-%m-%d"),
        "due_days": str(RETURN_INVOICE_DUE_DAYS),
        "item_name": item_names,
        "item_amount": ["1"] * count,
        "item_unit": ["Pauschale"] * count,
        "item_tax_type": ["E"] * count,
        "item_tax_amount": ["0"] * count,
        "item_single_price": item_prices,
        "email": organization.email,
        "street": organization.street_and_housenb,
        "zip": organization.zip_code,
        "city": organization.city,
        "country": "DE",
        "show_bankdata": True,
        "show_contactdata": True,
        "e_invoice_id": "0",
        "correspondence": (
            "Die Lastschrift konnte nicht eingezogen werden. Wir stellen Ihnen "
            "den Betrag zuzüglich der Gebühr für die Rücklastschrift in Rechnung."
        ),
        "final_provisions": (
            "Bitte überweisen Sie den Rechnungsbetrag mit Angabe der "
            "Rechnungsnummer als Verwendungszweck binnen "
            f"{RETURN_INVOICE_DUE_DAYS} Tagen."
        ),
    }


def invoice_returned_collection(user, collection: Collection) -> Collection:
    from .mails import send_return_invoice_email

    _require_manager(user, collection.agreement)
    if collection.status != Collection.Status.RETURNED:
        msg = _("Only returned collections can be invoiced.")
        raise AgreementError(msg)

    try:
        data = buchhaltungsbutler.create_einvoice(
            build_return_invoice_payload(collection)
        )
    except BuchhaltungsButlerError as error:
        logger.exception("Return invoice failed for collection %s", collection.id)
        msg = _("The invoice could not be created in the accounting system.")
        raise AgreementError(msg) from error

    with set_actor(user):
        collection.status = Collection.Status.INVOICED
        collection.invoice_number = str(data.get("invoicenumber", ""))
        collection.invoice_amount = collection.amount + settings.SEPA_RETURN_FEE
        collection.invoiced_at = timezone.now()
        collection.save()
    transaction.on_commit(lambda: send_return_invoice_email.enqueue(collection.id))
    return collection


def sync_invoice_payments(now: datetime | None = None) -> dict:
    """Set invoiced collections paid once the accounting system says so."""
    now = now or timezone.now()
    invoiced = list(
        Collection.objects.filter(status=Collection.Status.INVOICED).exclude(
            invoice_number=""
        )
    )
    if not invoiced:
        return {"status": "success", "paid": 0}
    try:
        receipts = buchhaltungsbutler.get_receipts()
    except BuchhaltungsButlerError:
        logger.exception("Could not read receipts for return invoices")
        return {"status": "error"}

    statuses = {
        str(row.get("invoicenumber")): str(row.get("payment_status", "")).lower()
        for row in receipts
    }
    paid = 0
    for collection in invoiced:
        if statuses.get(collection.invoice_number) in PAID_PAYMENT_STATUSES:
            collection.status = Collection.Status.PAID
            collection.paid_at = now
            collection.save(update_fields=["status", "paid_at"])
            paid += 1
    return {"status": "success", "paid": paid}


def mark_collection_paid(user, collection: Collection, note: str) -> Collection:
    _require_manager(user, collection.agreement)
    if collection.is_final:
        msg = _("This collection is already settled.")
        raise AgreementError(msg)
    with set_actor(user):
        collection.status = Collection.Status.PAID
        collection.paid_at = timezone.now()
        collection.status_note = note
        collection.save()
    return collection


def cancel_collection(user, collection: Collection, note: str) -> Collection:
    _require_manager(user, collection.agreement)
    if collection.is_final:
        msg = _("This collection is already settled.")
        raise AgreementError(msg)
    with set_actor(user):
        collection.status = Collection.Status.CANCELLED
        collection.status_note = note
        collection.save()
    return collection
