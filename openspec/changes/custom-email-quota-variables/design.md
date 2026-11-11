## Context

The free bookings quota (ADR 0023) leaves bookings untouched that existed before it was configured. The one-time transition `apply_free_bookings_quota(organization, dry_run=…)` brings them under the quota: per calendar year the earliest bookings keep the remaining free bookings, the rest is charged with the room's cheapest paid compensation or, without one, removed (series occurrences deleted, single bookings cancelled). In a dry run the same work is done inside a transaction and rolled back, and the `TransitionReport` lists `kept_free`, `charged` (with amounts), `deleted` and `cancelled`.

Custom emails are rendered per organization in `send_custom_organization_email` with a context built from the page filter (`from_date`, `to_date`, `resource_ids`). The existing statistics `number_of_bookings` and `total_amount` count confirmed bookings starting within the period on the selected resources.

## Goals / Non-Goals

**Goals:**

- An email can state how many bookings of the period lie above the free allowance, what they would cost and how many would be removed.
- The numbers equal what the transition will do for that organization.

**Non-Goals:**

- Changing the transition or the pricing.
- Bookings already priced against the quota (charged because the allowance was used up).
- Preview table columns or filters for the new values.

## Decisions

### 1. Reuse the transition dry run

A new function `get_quota_transition_preview(organization, from_date, to_date, resource_ids)` in `bookings/services_quota_transition.py` calls `apply_free_bookings_quota(organization, dry_run=True)` and reduces the report to three numbers.

- Why not re-implement the allocation as a query: the rules (allowance per year, remaining free bookings, cheapest fallback per room, removal without one) live in `price_booking` and the transition. A second implementation would drift, and the email would announce something the transition does not do.
- Cost: the dry run locks the organization row and saves and rolls back its legacy bookings. It runs once per email in the background worker, which is acceptable; see decision 3 for avoiding it when unused.

### 2. Allocation over the whole year, reporting within the filter

The dry run always covers all legacy bookings of the organization, because the allowance is per calendar year and across all rooms. The period and resource filter only select which of the resulting bookings are reported. A period of March therefore reports the March bookings that are above the limit after January and February have used their share.

The period uses the same rule as the existing statistics: start within `[from_date 00:00, to_date 23:59:59]` in the project time zone, open bounds allowed. `resource_ids` narrows to the selected rooms and parking lots; empty means all.

Mapping from the report:

| Tag | Source |
|---|---|
| `bookings_above_limit` | number of `charged` within the filter |
| `cost_above_limit` | sum of their `total_amount`, as a `Decimal` with two decimals |
| `bookings_above_limit_without_rate` | number of `deleted` plus `cancelled` within the filter |

`RemovedBooking` currently carries the resource only as a string; it gets the resource id so deleted occurrences can be filtered by resource.

### 3. Compute only when the email uses the tags

The task runs the preview only if the subject or body contains `above_limit`. Other custom emails are not slowed down and take no lock. When the tags are not used they are simply absent from the context.

- Alternative considered: lazy context values. More machinery for the same effect; a substring check on the two templates is enough.

### 4. Differences to the existing statistics are intended

`number_of_bookings` counts confirmed bookings, past or future. The new tags follow the transition instead: pending and confirmed, future, not invoiced, consuming compensation, not yet priced against the quota. The page help says so in one line. Organizations with an unlimited allowance, and organizations whose transition has already run, get 0 for all three.

### 5. Test-send needs no change

The test-send uses the same task with a recipient override, so the new tags can be checked there before the real send.

## Risks / Trade-offs

- [Numbers change between email and transition if bookings are added or cancelled in between] → inherent to an announcement; the email states a snapshot. Send close to the transition, or name the date in the text.
- [The dry run writes audit log entries or triggers side effects before rolling back] → it is the same dry run the management command already offers and its spec requires that nothing changes; the new tests assert that bookings are unchanged after rendering an email.
- [Many emails at once each lock one organization briefly] → one lock per organization, taken only by that organization's email; no contention between emails.
- [A manager expects the value to include bookings already charged] → the help text states that only bookings not yet priced against the quota count.
