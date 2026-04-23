import base64
import logging

import requests
from django.conf import settings
from django.tasks import task
from django.utils import timezone

logger = logging.getLogger(__name__)


@task(queue_name="default")
def create_draft_invoice(booking_id: int) -> dict:
    """Create a draft invoice in BuchhaltungsButler for a booking."""
    from re_sharing.bookings.models import Booking
    from re_sharing.bookings.services import build_invoice_payload

    booking = Booking.objects.select_related(
        "organization", "user", "resource", "compensation"
    ).get(id=booking_id)

    payload = build_invoice_payload(booking)
    payload["api_key"] = settings.BUCHHALTUNGSBUTLER_API_KEY

    credentials = base64.b64encode(
        f"{settings.BUCHHALTUNGSBUTLER_API_CLIENT}:{settings.BUCHHALTUNGSBUTLER_API_SECRET}".encode()
    ).decode()

    url = f"{settings.BUCHHALTUNGSBUTLER_BASE_URL}/invoices/create/draft"

    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        if not response.ok:
            logger.error(
                "BuchhaltungsButler returned %s for booking %s: %s",
                response.status_code,
                booking_id,
                response.text,
            )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to create draft invoice for booking %s", booking_id)
        return {"booking_id": booking_id, "status": "error"}
    else:
        logger.info("Draft invoice created for booking %s", booking_id)
        return {"booking_id": booking_id, "status": "success"}


@task(queue_name="default")
def create_einvoice(booking_id: int) -> dict:
    """Create an e-invoice in BuchhaltungsButler and save the invoice number."""
    from re_sharing.bookings.models import Booking
    from re_sharing.bookings.services import build_einvoice_payload

    booking = Booking.objects.select_related(
        "organization", "user", "resource", "compensation"
    ).get(id=booking_id)

    payload = build_einvoice_payload(booking)
    payload["api_key"] = settings.BUCHHALTUNGSBUTLER_API_KEY

    credentials = base64.b64encode(
        f"{settings.BUCHHALTUNGSBUTLER_API_CLIENT}:{settings.BUCHHALTUNGSBUTLER_API_SECRET}".encode()
    ).decode()

    url = f"{settings.BUCHHALTUNGSBUTLER_BASE_URL}/invoices/create/einvoice"

    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        if not response.ok:
            logger.error(
                "BuchhaltungsButler returned %s for booking %s: %s",
                response.status_code,
                booking_id,
                response.text,
            )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        logger.exception("Failed to create e-invoice for booking %s", booking_id)
        return {"booking_id": booking_id, "status": "error"}

    if data.get("success"):
        invoice_number = data.get("invoicenumber", "")
        booking.invoice_number = invoice_number
        booking.save(update_fields=["invoice_number"])
        logger.info(
            "E-invoice created for booking %s, invoice number: %s",
            booking_id,
            invoice_number,
        )
        return {
            "booking_id": booking_id,
            "status": "success",
            "invoice_number": invoice_number,
        }

    logger.error(
        "E-invoice creation failed for booking %s: %s",
        booking_id,
        data.get("message", "unknown error"),
    )
    return {"booking_id": booking_id, "status": "error", "message": data.get("message")}


@task(queue_name="default")
def create_org_draft_invoice(organization_id: int) -> dict:
    """Create a bundled draft invoice for all uninvoiced bookings of an org."""
    from re_sharing.bookings.models import Booking
    from re_sharing.bookings.services import build_org_invoice_payload
    from re_sharing.organizations.models import Organization
    from re_sharing.utils.models import BookingStatus

    organization = Organization.objects.get(id=organization_id)

    bookings = list(
        Booking.objects.filter(
            organization=organization,
            status=BookingStatus.CONFIRMED,
            total_amount__gt=0,
            invoice_number="",
            timespan__endswith__lt=timezone.now(),
        )
        .exclude(invoice_address__contains={"single_invoice": True})
        .exclude(resource__type="lendable_item")
        .select_related("resource", "compensation")
        .order_by("timespan")
    )

    if not bookings:
        return {"organization_id": organization_id, "status": "no_bookings"}

    payload = build_org_invoice_payload(organization, bookings)
    payload["api_key"] = settings.BUCHHALTUNGSBUTLER_API_KEY

    credentials = base64.b64encode(
        f"{settings.BUCHHALTUNGSBUTLER_API_CLIENT}:{settings.BUCHHALTUNGSBUTLER_API_SECRET}".encode()
    ).decode()

    url = f"{settings.BUCHHALTUNGSBUTLER_BASE_URL}/invoices/create/draft"

    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30,
        )
        if not response.ok:
            logger.error(
                "BuchhaltungsButler returned %s for org %s: %s",
                response.status_code,
                organization_id,
                response.text,
            )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception(
            "Failed to create org draft invoice for org %s", organization_id
        )
        return {"organization_id": organization_id, "status": "error"}
    else:
        logger.info(
            "Org draft invoice created for org %s (%d bookings)",
            organization_id,
            len(bookings),
        )
        return {
            "organization_id": organization_id,
            "status": "success",
            "booking_count": len(bookings),
        }
