## Context

The free bookings quota (ADR 0023) limits how many free bookings an organization gets per calendar year. A booking consumes one when its compensation has `counts_against_free_bookings`. The flag is read in several places:

- `price_booking` and `series_needs_fallback` in `bookings/services_pricing.py`
- `_exceeds_free_bookings` and `save_booking` in `bookings/services.py`
- `get_bookable_compensations` in `resources/selectors.py`
- the compensation partial view in `resources/views.py` and its template
- `get_legacy_consuming_bookings` and `get_legacy_consuming_series` in `bookings/services_quota_transition.py`

Compensations are shared between resources and tied to organization groups, so excluding one resource today means splitting every free compensation that covers it.

## Goals / Non-Goals

**Goals:**

- One switch on a resource that takes all its bookings out of the quota, for every organization and compensation.
- The same answer everywhere: pricing, bookability, the booking form, the transition and the email tags.
- No behaviour change until the switch is set.

**Non-Goals:**

- Exemption per location or per organization group.
- Re-pricing existing bookings when the switch changes.
- Exposing the switch in the manager's resource form.

## Decisions

### D1: Boolean `exempt_from_free_bookings` on `Resource`, default false

The default keeps today's behaviour, so no data migration is needed. The name states the exception, which is the rare case.

Alternative considered: an inverted `counts_against_free_bookings` on the resource, mirroring the compensation. Rejected: two flags with the same name and "both must be true" semantics are easy to misread, and a default of true would have to be backfilled.

### D2: One shared predicate

`consumes_free_booking(compensation, resource)` in `services_pricing.py` returns `compensation.counts_against_free_bookings and not resource.exempt_from_free_bookings`. `price_booking`, `series_needs_fallback`, `_exceeds_free_bookings` and `save_booking` call it instead of reading the compensation flag. `price_booking` takes the resource from `booking.resource`.

Alternative considered: checking the resource inside `get_remaining_free_bookings` and returning `None` (unlimited). Rejected: that selector answers a question about the organization and year, and the dashboard uses it without a resource.

### D3: On an exempt resource a flagged compensation behaves like an unflagged one

The booking is free (`total_amount` empty), `uses_free_booking` stays false, and it is possible with zero free bookings left. No new pricing path is added; the consuming branch is simply not entered.

### D4: Booking form

`get_bookable_compensations` returns all compensations and `None` as remaining count for an exempt resource. `None` already means "do not show a hint", so the template needs no new variable. The view offers no fallback compensations for a series on an exempt resource.

### D5: The transition skips exempt resources entirely

`get_legacy_consuming_bookings` and `get_legacy_consuming_series` exclude exempt resources. The bookings are neither kept free against the allowance nor charged nor removed, and they take no place in the chronological allocation. Their series keep `is_quota_priced` false and get no fallback.

The transition command is idempotent, so if a resource stops being exempt later, running it again brings that resource's legacy bookings and series under the quota.

Alternative considered: marking series on exempt resources as quota-priced without a fallback. Rejected: a later removal of the exemption would then drop their occurrences beyond the allowance without anyone having chosen a fallback.

### D6: Changing the switch affects only bookings priced afterwards

This follows the existing rules "changes to the allowance affect only later bookings" and "existing bookings are not re-priced". A booking that already has `uses_free_booking` true keeps it and still counts as used after its resource becomes exempt; a free booking made while the resource was exempt stays unmarked after the exemption is removed. Editing such a booking re-prices it only under the existing conditions (organization, compensation or year changes).

### D7: Admin only

The switch is added to the resource admin (field, list column, filter), like the compensation flag. The manager's resource form is unchanged.

### D8: ADR

A short ADR 0027 records D1, D3, D5 and D6 and refers to ADR 0023.

## Risks / Trade-offs

- Free bookings already consumed on a resource stay consumed when it becomes exempt → acceptable before the quota starts, because the transition has not run and few bookings carry the mark; a staff member can clear `uses_free_booking` on single bookings in the admin.
- A flagged compensation on an exempt resource looks like it counts in the admin → the help text of both fields names the other one.
- A place that reads the compensation flag directly is missed → the tasks list every current reader, and a test per reader covers the exempt case.
- Legacy series on a resource whose exemption is removed keep legacy pricing until the transition is run again → documented in the ADR and in the command's help.

## Migration Plan

1. Deploy with the schema migration; nothing changes.
2. Set the switch on the resources that should not count, before announcing numbers by email and before running the transition.
3. Rollback: unset the switch, or revert the deployment; the column can stay.

## Open Questions

- Should bookings that already use a free booking be released when their resource becomes exempt? The design says no (D6). If yes, it is a small addition to the admin action or a one-off command.
