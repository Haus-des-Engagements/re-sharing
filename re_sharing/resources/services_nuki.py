import logging
import time
from datetime import datetime
from datetime import timedelta

import requests
from django.conf import settings
from django.db.models import Q
from django.tasks import task
from django.utils import timezone

logger = logging.getLogger(__name__)

NUKI_API_BASE = "https://api.nuki.io"
NUKI_AUTH_TYPE_CODE = 13
HTTP_409_CONFLICT = 409


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


def _get_existing_keypad_codes(smartlock_id: str) -> dict[int, dict]:
    """Get all existing keypad codes from a smartlock.

    Returns:
        Dict mapping code number (int) to auth data dict with keys:
        - id: auth ID
        - name: auth name
        - allowedFromDate: start time
        - allowedUntilDate: end time
    """
    resp = requests.get(
        f"{NUKI_API_BASE}/smartlock/{smartlock_id}/auth",
        headers=_nuki_headers(),
        timeout=15,
    )
    resp.raise_for_status()

    auths = resp.json()
    existing_codes = {}
    for auth in auths:
        if str(auth.get("type")) == str(NUKI_AUTH_TYPE_CODE):
            code_num = int(auth.get("code", 0))
            if code_num:
                existing_codes[code_num] = {
                    "id": str(auth["id"]),
                    "name": auth.get("name", ""),
                    "allowedFromDate": auth.get("allowedFromDate", ""),
                    "allowedUntilDate": auth.get("allowedUntilDate", ""),
                }

    return existing_codes


def _delete_keypad_codes_by_ids(auth_ids: list[str]) -> int:
    """Bulk-delete keypad codes by their auth IDs."""
    if not auth_ids:
        return 0

    del_resp = requests.delete(
        f"{NUKI_API_BASE}/smartlock/auth",
        headers=_nuki_headers(),
        json=auth_ids,
        timeout=15,
    )
    del_resp.raise_for_status()
    logger.info("Bulk-deleted %d keypad codes", len(auth_ids))
    return len(auth_ids)


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
        valid_until = pc.validity_end  # None if no expiration
        name = f"PC-{pc.pk}"
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
        name = f"B-{booking.pk}"
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


def _build_desired_state(code_to_smartlocks: dict) -> dict:
    """Build desired state from code mappings.

    Args:
        code_to_smartlocks: Dict of {(code, name, valid_from, valid_until):
            set of smartlock_ids}

    Returns:
        Dict of {(code_num, smartlock_id): payload_data}
    """
    desired_state = {}
    for (
        code,
        name,
        valid_from,
        valid_until,
    ), smartlock_ids in code_to_smartlocks.items():
        for sl_id in smartlock_ids:
            key = (int(code), sl_id)
            if key not in desired_state:  # Deduplication
                payload_data = {
                    "code": int(code),
                    "name": name,
                    "allowedFromDate": valid_from.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                }
                # Only include allowedUntilDate if there's an expiration
                if valid_until is not None:
                    payload_data["allowedUntilDate"] = valid_until.strftime(
                        "%Y-%m-%dT%H:%M:%S.000Z"
                    )
                desired_state[key] = payload_data
    return desired_state


def _normalize_nuki_datetime(dt_str: str) -> str:
    """Normalize NUKI datetime string for comparison.

    The API might return dates in slightly different formats.
    Parse and re-format to ensure consistent comparison.
    """
    if not dt_str:
        return ""
    try:
        # Parse ISO format datetime (handles both Z and timezone offsets)
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        # Return in our standard format
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except (ValueError, AttributeError):
        # If parsing fails, return original string
        return dt_str


def _compare_and_plan_changes(
    existing_codes_by_smartlock: dict, desired_state: dict
) -> tuple[list[str], dict]:
    """Compare existing vs desired codes and plan changes.

    Returns:
        Tuple of (auth_ids_to_delete, codes_to_add)
        where codes_to_add is {code_num: {smartlock_ids: [...], payload_data: {...}}}
    """
    auth_ids_to_delete = []
    codes_to_add = {}

    # Track reasons for deletion
    deleted_not_desired = 0
    deleted_for_update = 0
    kept_unchanged = 0

    # Check existing codes - delete if not desired or if validity changed
    for smartlock_id, existing_codes in existing_codes_by_smartlock.items():
        for code_num, auth_data in existing_codes.items():
            key = (code_num, smartlock_id)
            if key not in desired_state:
                # Code exists but shouldn't - delete it
                auth_ids_to_delete.append(auth_data["id"])
                deleted_not_desired += 1
                logger.debug(
                    "Will delete code %s from smartlock %s (not desired)",
                    code_num,
                    smartlock_id,
                )
            else:
                # Code exists and is desired - check if validity matches
                desired = desired_state[key]

                # Normalize datetimes for comparison
                existing_from = _normalize_nuki_datetime(auth_data["allowedFromDate"])
                existing_until = _normalize_nuki_datetime(
                    auth_data.get("allowedUntilDate", "")
                )
                desired_from = desired["allowedFromDate"]
                desired_until = desired.get("allowedUntilDate", "")

                # Compare - treat empty/missing as equivalent for until date
                from_changed = existing_from != desired_from
                # Only consider until date changed if both are non-empty and different
                both_have_until = existing_until and desired_until
                until_changed = both_have_until and existing_until != desired_until

                if from_changed or until_changed:
                    # Validity changed - delete and re-add
                    auth_ids_to_delete.append(auth_data["id"])
                    deleted_for_update += 1
                    logger.debug(
                        "Will update code %s on smartlock %s (validity changed: "
                        "from %s-%s to %s-%s)",
                        code_num,
                        smartlock_id,
                        existing_from,
                        existing_until,
                        desired_from,
                        desired_until,
                    )
                    # Mark for re-adding
                    if code_num not in codes_to_add:
                        codes_to_add[code_num] = {
                            "smartlock_ids": [],
                            "payload_data": desired,
                        }
                    codes_to_add[code_num]["smartlock_ids"].append(smartlock_id)
                else:
                    # Code exists with correct validity - keep it
                    kept_unchanged += 1
                    logger.debug(
                        "Keeping existing code %s on smartlock %s (unchanged)",
                        code_num,
                        smartlock_id,
                    )

    # Check desired codes - add if not existing
    for (code_num, smartlock_id), payload_data in desired_state.items():
        existing = existing_codes_by_smartlock.get(smartlock_id, {})
        if code_num not in existing:
            # Code is desired but doesn't exist - add it
            if code_num not in codes_to_add:
                codes_to_add[code_num] = {
                    "smartlock_ids": [],
                    "payload_data": payload_data,
                }
            codes_to_add[code_num]["smartlock_ids"].append(smartlock_id)

    logger.info(
        "Comparison summary: keeping %d unchanged, deleting %d (not desired), "
        "updating %d (validity changed)",
        kept_unchanged,
        deleted_not_desired,
        deleted_for_update,
    )

    return auth_ids_to_delete, codes_to_add


def _push_all_codes(payloads: list[dict]) -> None:
    """Push all keypad codes to smartlocks (one request per code)."""
    if not payloads:
        logger.info("No codes to push")
        return

    # The API expects individual PUT requests for each code, not a bulk array
    for i, payload in enumerate(payloads, 1):
        try:
            resp = requests.put(
                f"{NUKI_API_BASE}/smartlock/auth",
                headers=_nuki_headers(),
                json=payload,  # Send single code object
                timeout=30,
            )
            resp.raise_for_status()
            logger.debug(
                "Pushed code %d/%d (code=%s) to smartlocks %s",
                i,
                len(payloads),
                payload["code"],
                payload["smartlockIds"],
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == HTTP_409_CONFLICT:
                logger.exception(
                    "409 Conflict when pushing code %s to smartlocks %s. "
                    "Code may already exist. Payload: %s",
                    payload["code"],
                    payload["smartlockIds"],
                    payload,
                )
            raise

    logger.info("Successfully pushed %d codes across all smartlocks", len(payloads))


@task(queue_name="default")
def sync_all_smartlock_codes() -> dict:
    """
    Sync all keypad codes for ALL smartlocks using smart diff-based sync:
    1. Fetches existing codes from all smartlocks
    2. Determines desired codes from today's bookings and permanent codes
    3. Deletes only codes that shouldn't exist or have wrong validity
    4. Adds only codes that are missing
    5. Updates codes that need different validity times

    This is more efficient than bulk delete + re-add.
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
        return {"smartlocks": 0, "added": 0, "deleted": 0, "skipped": 0}

    # Fetch existing codes from all smartlocks
    existing_codes_by_smartlock = {}
    for smartlock_id in all_smartlock_ids:
        existing_codes_by_smartlock[smartlock_id] = _get_existing_keypad_codes(
            smartlock_id
        )
        logger.debug(
            "Smartlock %s has %d existing keypad codes",
            smartlock_id,
            len(existing_codes_by_smartlock[smartlock_id]),
        )

    # Collect desired codes from bookings and permanent codes
    all_accesses = Access.objects.exclude(smartlock_id="")
    permanent_codes = list(_get_active_permanent_codes_for_accesses(all_accesses))
    bookings = list(_get_todays_confirmed_bookings_for_accesses(all_accesses))

    orgs_with_permanent_code = {
        pc.organization_id for pc in permanent_codes if pc.organization_id
    }

    # Build code mappings - this gives us the desired state
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

    # Build desired state and compare with existing to plan changes
    desired_state = _build_desired_state(code_to_smartlocks)
    logger.info(
        "Desired state: %d unique (code, smartlock) combinations", len(desired_state)
    )
    auth_ids_to_delete, codes_to_add = _compare_and_plan_changes(
        existing_codes_by_smartlock, desired_state
    )
    logger.info(
        "Plan: delete %d auth IDs, add %d unique codes",
        len(auth_ids_to_delete),
        len(codes_to_add),
    )

    # Delete outdated/wrong codes
    deleted = _delete_keypad_codes_by_ids(auth_ids_to_delete)

    # Wait for NUKI API to propagate deletions (eventual consistency)
    if deleted > 0:
        logger.info(
            "Waiting 10 seconds for NUKI API to propagate %d deletions...", deleted
        )
        time.sleep(10)

    # Re-fetch existing codes after deletion to verify and filter
    # This prevents 409 errors if delete didn't fully propagate
    logger.debug("Re-fetching existing codes after deletion to verify...")
    existing_after_delete = {}
    for smartlock_id in all_smartlock_ids:
        existing_after_delete[smartlock_id] = _get_existing_keypad_codes(smartlock_id)

    # Filter out codes that still exist after deletion
    payloads = []
    skipped_still_exist = 0
    for data in codes_to_add.values():
        code_num = data["payload_data"]["code"]
        smartlock_ids = data["smartlock_ids"]

        # Check if code still exists on any target smartlock
        filtered_smartlocks = [
            sl_id
            for sl_id in smartlock_ids
            if code_num not in existing_after_delete.get(sl_id, {})
        ]

        if filtered_smartlocks:
            payload = data["payload_data"].copy()
            payload["smartlockIds"] = filtered_smartlocks
            payload["type"] = NUKI_AUTH_TYPE_CODE
            payload["allowedWeekDays"] = 127
            payloads.append(payload)

            if len(filtered_smartlocks) < len(smartlock_ids):
                logger.warning(
                    "Code %s still exists on some smartlocks after deletion, "
                    "only adding to: %s (originally: %s)",
                    code_num,
                    filtered_smartlocks,
                    smartlock_ids,
                )
        else:
            logger.warning(
                "Code %s still exists on all target smartlocks after deletion, "
                "skipping add",
                code_num,
            )
            skipped_still_exist += 1

    _push_all_codes(payloads)
    added = len(payloads)

    logger.info(
        "Synced %d smartlock(s): added %d codes, deleted %d codes, "
        "skipped %d bookings (permanent code org), "
        "%d codes still existed after delete",
        len(all_smartlock_ids),
        added,
        deleted,
        skipped,
        skipped_still_exist,
    )
    return {
        "smartlocks": len(all_smartlock_ids),
        "added": added,
        "deleted": deleted,
        "skipped": skipped,
        "skipped_still_exist": skipped_still_exist,
    }
