"""Client for the REST API of the accounting system (v1).

Every call is a POST with HTTP basic auth (API client and secret) and the API
key in the JSON payload. All failures, whether network, HTTP status or a
response with ``success: false``, raise ``BuchhaltungsButlerError``.
"""

import base64
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30
PAGE_SIZE = 500


class BuchhaltungsButlerError(Exception):
    """The accounting system could not be reached or refused the request.

    ``api_message`` holds the message of a response with ``success: false``.
    """

    def __init__(self, message: str, api_message: str | None = None):
        super().__init__(message)
        self.api_message = api_message


def _headers() -> dict:
    credentials = base64.b64encode(
        f"{settings.BUCHHALTUNGSBUTLER_API_CLIENT}:"
        f"{settings.BUCHHALTUNGSBUTLER_API_SECRET}".encode()
    ).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(path: str, payload: dict) -> dict:
    url = f"{settings.BUCHHALTUNGSBUTLER_BASE_URL}{path}"
    body = {**payload, "api_key": settings.BUCHHALTUNGSBUTLER_API_KEY}
    try:
        response = requests.post(
            url, json=body, headers=_headers(), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as error:
        msg = f"Request to {path} failed: {error}"
        raise BuchhaltungsButlerError(msg) from error

    if not response.ok:
        logger.error(
            "Accounting system returned %s for %s: %s",
            response.status_code,
            path,
            response.text,
        )
        msg = f"{path} returned HTTP {response.status_code}"
        raise BuchhaltungsButlerError(msg)

    try:
        data = response.json()
    except ValueError as error:
        msg = f"{path} returned no JSON"
        raise BuchhaltungsButlerError(msg) from error

    if isinstance(data, dict) and data.get("success") is False:
        api_message = data.get("message")
        msg = f"{path} failed: {api_message or 'unknown error'}"
        raise BuchhaltungsButlerError(msg, api_message=api_message)
    return data


def _get_all(path: str, payload: dict) -> list[dict]:
    """Collect every row of a paged list endpoint."""
    rows: list[dict] = []
    offset = 0
    while True:
        data = _post(path, {**payload, "limit": PAGE_SIZE, "offset": offset})
        page = data.get("data") or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def create_draft_invoice(payload: dict) -> dict:
    return _post("/invoices/create/draft", payload)


def create_einvoice(payload: dict) -> dict:
    """Create a final e-invoice; the response carries ``invoicenumber``."""
    return _post("/invoices/create/einvoice", payload)


def get_receipts(**filters) -> list[dict]:
    """Outbound receipts (invoices) with their ``payment_status``."""
    return _get_all("/receipts/get", {"list_direction": "outbound", **filters})


def get_transactions(*, date_since_last_modified: str | None = None) -> list[dict]:
    """Bank transactions, optionally only those changed since a timestamp."""
    filters = {}
    if date_since_last_modified:
        filters["date_since_last_modified"] = date_since_last_modified
    return _get_all("/transactions/get", filters)
