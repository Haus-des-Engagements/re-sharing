import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db.models import Q
from django.tasks import task
from django.utils import timezone

logger = logging.getLogger(__name__)

NUKI_API_BASE = "https://api.nuki.io"
NUKI_AUTH_TYPE_CODE = 13


def _nuki_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.NUKI_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _get_accesses_for_smartlock(smartlock_id: str):
    """
    Return all Access objects that contribute codes to this smartlock.

    Example: Access A (smartlock_id=1, parent_access=B), Access B (smartlock_id=2)
    When syncing smartlock_id=1, we need codes from both A and B (the parent).

    Returns:
    - The access directly configured with this smartlock_id
    - Its parent access (if it has one), since parent codes should also
      work on child locks
    """
    from re_sharing.resources.models import Access

    # The access with this smartlock_id
    access = Access.objects.filter(smartlock_id=smartlock_id).first()
    if not access:
        return Access.objects.none()

    accesses = [access]

    # Add the parent access if it exists
    if access.parent_access:
        accesses.append(access.parent_access)

    return Access.objects.filter(id__in=[a.id for a in accesses])


def _get_todays_confirmed_bookings_for_accesses(accesses):
    """Return confirmed bookings starting today for resources in the given accesses."""
    from re_sharing.bookings.models import Booking
    from re_sharing.utils.models import BookingStatus

    today = timezone.now().date()
    return Booking.objects.filter(
        resource__access__in=accesses,
        status=BookingStatus.CONFIRMED,
        timespan__startswith__date=today,
    ).select_related("organization", "resource__access")


def _get_active_permanent_codes_for_accesses(accesses):
    """Return currently active permanent codes for the given accesses."""
    from re_sharing.resources.models import PermanentCode

    now = timezone.now()
    return (
        PermanentCode.objects.filter(
            accesses__in=accesses,
            validity_start__lte=now,
        )
        .filter(Q(validity_end__isnull=True) | Q(validity_end__gte=now))
        .select_related("organization")
        .distinct()
    )


def _delete_all_keypad_codes(smartlock_id: str) -> int:
    """Bulk-delete all keypad (type=13) authorizations from a NUKI smartlock."""
    resp = requests.get(
        f"{NUKI_API_BASE}/smartlock/{smartlock_id}/auth",
        headers=_nuki_headers(),
        timeout=15,
    )
    resp.raise_for_status()

    ids_to_delete = [
        str(auth["id"])
        for auth in resp.json()
        if auth.get("type") == NUKI_AUTH_TYPE_CODE
    ]

    if not ids_to_delete:
        logger.debug("No keypad codes to delete from smartlock %s", smartlock_id)
        return 0

    del_resp = requests.delete(
        f"{NUKI_API_BASE}/smartlock/auth",
        headers=_nuki_headers(),
        json=ids_to_delete,
        timeout=15,
    )
    del_resp.raise_for_status()
    logger.info(
        "Bulk-deleted %d keypad codes from smartlock %s",
        len(ids_to_delete),
        smartlock_id,
    )
    return len(ids_to_delete)


def _build_code_payload(
    smartlock_ids: list[str], code: str, name: str, valid_from, valid_until
) -> dict:
    """Build a single code payload for the API."""
    return {
        "name": name[:100],
        "type": NUKI_AUTH_TYPE_CODE,  # Integer, not string
        "code": int(code),  # Integer, not string
        "smartlockIds": smartlock_ids,
        "allowedFromDate": valid_from.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "allowedUntilDate": valid_until.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "allowedWeekDays": 127,  # All days (bitfield: 1111111)
    }


def _collect_permanent_codes_mapping(permanent_codes) -> dict:
    """Build mapping of permanent codes to their smartlock IDs."""
    code_to_smartlocks = {}

    for pc in permanent_codes:
        valid_from = pc.validity_start
        valid_until = pc.validity_end or (timezone.now() + timedelta(days=365 * 10))
        name = pc.name or f"Permanent {pc.id}"
        key = (pc.code, name, valid_from, valid_until)

        if key not in code_to_smartlocks:
            code_to_smartlocks[key] = set()

        # Add all smartlocks that have accesses associated with this code
        for access in pc.accesses.all():
            if access.smartlock_id:
                code_to_smartlocks[key].add(access.smartlock_id)
            # Also add parent smartlock if exists
            if access.parent_access and access.parent_access.smartlock_id:
                code_to_smartlocks[key].add(access.parent_access.smartlock_id)

    return code_to_smartlocks


def _collect_booking_codes_mapping(
    bookings, orgs_with_permanent_code
) -> tuple[dict, int]:
    """Build mapping of booking codes to their smartlock IDs.

    Returns:
        Tuple of (code_to_smartlocks dict, skipped_count)
    """
    code_to_smartlocks = {}
    skipped = 0

    for booking in bookings:
        if booking.organization_id in orgs_with_permanent_code:
            logger.debug(
                "Skipping booking %s - org %s has a permanent code",
                booking.slug,
                booking.organization,
            )
            skipped += 1
            continue

        valid_from = booking.timespan.lower - timedelta(hours=1)
        valid_until = booking.timespan.upper + timedelta(hours=1)
        name = f"{booking.organization.name} - {booking.slug}"
        key = (booking.access_code, name, valid_from, valid_until)

        if key not in code_to_smartlocks:
            code_to_smartlocks[key] = set()

        # Add smartlock IDs from the booking's resource access
        access = booking.resource.access
        if access and access.smartlock_id:
            code_to_smartlocks[key].add(access.smartlock_id)
        # Also add parent smartlock if exists
        if access and access.parent_access and access.parent_access.smartlock_id:
            code_to_smartlocks[key].add(access.parent_access.smartlock_id)

    return code_to_smartlocks, skipped


def _build_payloads_with_deduplication(
    code_to_smartlocks: dict,
) -> tuple[list[dict], int]:
    """Build code payloads, deduplicating by (code_number, smartlock_id).

    Returns:
        Tuple of (payloads list, skipped_duplicates count)
    """
    pushed_combinations = set()
    payloads = []
    skipped_duplicates = 0

    for (
        code,
        name,
        valid_from,
        valid_until,
    ), smartlock_ids in code_to_smartlocks.items():
        if not smartlock_ids:
            continue

        # Filter out smartlocks that already have this code number
        smartlock_ids_to_push = []
        for sl_id in smartlock_ids:
            if (code, sl_id) not in pushed_combinations:
                smartlock_ids_to_push.append(sl_id)
                pushed_combinations.add((code, sl_id))
            else:
                logger.debug(
                    "Skipping duplicate: code %s already pushed to smartlock %s",
                    code,
                    sl_id,
                )
                skipped_duplicates += 1

        if smartlock_ids_to_push:
            payloads.append(
                _build_code_payload(
                    smartlock_ids_to_push, code, name, valid_from, valid_until
                )
            )

    return payloads, skipped_duplicates


def _push_all_codes(payloads: list[dict]) -> None:
    """Push all keypad codes to smartlocks (one request per code)."""
    if not payloads:
        logger.info("No codes to push")
        return

    # The API expects individual PUT requests for each code, not a bulk array
    for i, payload in enumerate(payloads, 1):
        resp = requests.put(
            f"{NUKI_API_BASE}/smartlock/auth",
            headers=_nuki_headers(),
            json=payload,  # Send single code object
            timeout=30,
        )
        resp.raise_for_status()
        logger.debug(
            "Pushed code %d/%d to smartlocks %s",
            i,
            len(payloads),
            payload["smartlockIds"],
        )

    logger.info("Successfully pushed %d codes across all smartlocks", len(payloads))


@task(queue_name="default")
def sync_all_smartlock_codes() -> dict:
    """
    Sync all keypad codes for ALL smartlocks for today in a single pass:
    1. Deletes all existing keypad codes from all smartlocks.
    2. Groups codes by (code, valid_from, valid_until, name) and collects all
       smartlock IDs that need each code.
    3. Pushes each unique code once with all relevant smartlockIds.

    This avoids 409 conflicts from pushing the same code to the same smartlock twice.
    """
    from re_sharing.resources.models import Access

    # Get all smartlocks
    all_smartlock_ids = list(
        Access.objects.exclude(smartlock_id="")
        .values_list("smartlock_id", flat=True)
        .distinct()
    )

    if not all_smartlock_ids:
        logger.warning("No smartlocks configured — skipping sync")
        return {"smartlocks": 0, "pushed": 0, "skipped": 0}

    # Delete all keypad codes from all smartlocks
    for smartlock_id in all_smartlock_ids:
        _delete_all_keypad_codes(smartlock_id)

    # Collect all accesses across all smartlocks
    all_accesses = Access.objects.exclude(smartlock_id="")
    permanent_codes = list(_get_active_permanent_codes_for_accesses(all_accesses))
    bookings = list(_get_todays_confirmed_bookings_for_accesses(all_accesses))

    orgs_with_permanent_code = {
        pc.organization_id for pc in permanent_codes if pc.organization_id
    }

    # Build code mappings
    code_to_smartlocks = _collect_permanent_codes_mapping(permanent_codes)
    booking_codes, skipped = _collect_booking_codes_mapping(
        bookings, orgs_with_permanent_code
    )

    # Merge booking codes into the main mapping
    for key, smartlock_ids in booking_codes.items():
        if key not in code_to_smartlocks:
            code_to_smartlocks[key] = smartlock_ids
        else:
            code_to_smartlocks[key].update(smartlock_ids)

    # Build payloads with deduplication
    payloads, skipped_duplicates = _build_payloads_with_deduplication(
        code_to_smartlocks
    )

    # Push all codes
    _push_all_codes(payloads)
    pushed = len(payloads)

    logger.info(
        "Synced %d smartlock(s): pushed %d unique codes, "
        "skipped %d bookings (permanent code org), "
        "%d duplicate code numbers",
        len(all_smartlock_ids),
        pushed,
        skipped,
        skipped_duplicates,
    )
    return {
        "smartlocks": len(all_smartlock_ids),
        "pushed": pushed,
        "skipped": skipped,
        "skipped_duplicates": skipped_duplicates,
    }
