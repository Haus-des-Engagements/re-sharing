import base64
import logging

import requests
from django.conf import settings
from django.tasks import task

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
