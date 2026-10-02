## Context

ADR 0023 introduced the quota with `Booking.uses_free_booking`, `BookingSeries.is_quota_priced`, `BookingSeries.fallback_compensation`, the selectors in `organizations/selectors.py` and `resources/selectors.py`, and `price_booking` in `bookings/services_pricing.py`. Bookings that existed when the quota was configured stay unflagged and uncounted; legacy series keep the series compensation in `generate_bookings`. The rollout plan (archived change `free-bookings-quota`, Migration Plan step 6) foresees one management command, run once after the announcement grace period, instead of a manager UI.

Constraints:

- Must be safe to run on production data and to run twice.
- Must not touch bookings that already happened, are invoiced, or belong to organizations whose allowance is unlimited.
- HackSoft style: the command is thin, the work lives in a service module with tests.

## Goals / Non-Goals

**Goals:**

- Bring the remaining legacy bookings of limited organizations under the quota in one command run, with a dry run and a readable report.
- Deterministic allocation that a manager can explain to an organization.
- Legacy series behave like new series afterwards (fallback set, `is_quota_priced` true).

**Non-Goals:**

- Manager views, previews or per-organization buttons.
- Emails to organizations; managers inform the few affected ones by hand with the report.
- Re-pricing past or invoiced bookings.
- Changing the quota rules themselves.

## Decisions

### D1: One service function per organization, the command loops

`apply_free_bookings_quota(organization, *, dry_run=False) -> TransitionReport` in a new module `bookings/services_quota_transition.py`. It locks the organization row (`select_for_update`) inside `transaction.atomic()`, does the work and, in dry run, calls `transaction.set_rollback(True)` before returning so the report reflects the real outcome without persisting it. The management command `apply_free_bookings_quota` resolves the organizations, calls the service per organization and prints the reports.

Why per organization: the lock matches D8 of the quota change, a failing organization does not roll back the others, and the report is naturally per organization.

### D2: Which organizations and which bookings

Organizations: all confirmed organizations whose effective allowance is limited at some date, found through the groups that carry `free_bookings_per_year` and filtered with `get_free_bookings_allowance(organization, group.free_bookings_valid_from)` is not `None` (a member group would make it unlimited). `--organizations slug ...` restricts the run.

Legacy bookings of an organization: status pending or confirmed, `uses_free_booking` false, `invoice_number` empty, compensation with `counts_against_free_bookings`, start in the future (`timespan__startswith__gt=now`) and a limited allowance on `start_date`. Both standalone bookings and occurrences of series with `is_quota_priced` false qualify. Occurrences with status unavailable are not selected; they are never priced.

Why `start_date` with a limited allowance rather than a fixed date: an organization can sit in several limited groups with different valid-from dates; the selector already answers the question per date.

### D3: Chronological allocation per year

Per calendar year the legacy bookings are sorted by start, and the first `remaining` of them get `uses_free_booking = True`, where `remaining = get_remaining_free_bookings(organization, date)` already accounts for quota-priced bookings created since the configuration. This is a deliberate exception to "first created, first served" (ADR 0023): none of these bookings were created under the rule, so the earliest dates are the fairest and the easiest to explain.

Alternative considered: letting the organization choose which dates stay free. Rejected; the organization can still cancel charged dates afterwards through the existing cancel flow, which gives the same freedom without tooling.

### D4: Fallback is the cheapest paid compensation of the room

For the bookings beyond the allowance, the fallback for a resource is `get_paid_fallback_compensations(organization, resource).order_by("hourly_rate").first()`. The booking is priced with `price_booking(booking, compensation, fallback_compensation=fallback, reserved=...)` so the rules and the amount calculation are the ones of the quota change. The same fallback is stored on the organization's legacy series for that room together with `is_quota_priced = True`, also when all current occurrences stayed free, so that the nightly extension prices later occurrences correctly.

Why cheapest: the command has no manager in the loop to choose; the cheapest option is the one no organization will object to, and a manager can change the fallback of a series in the admin afterwards.

### D5: No fallback means removal, matching the quota rules

Where the room has no paid compensation (second location), occurrences beyond the allowance are deleted, as `generate_bookings` does for new series, and standalone bookings are cancelled (status cancelled, which returns nothing because they were never flagged). The report lists both. No emails are sent; a standalone booking cancelled this way is exactly what the manager tells the organization about.

Alternative considered: leaving such bookings free. Rejected because it would keep the second location unlimited for legacy bookers, which the board decided against.

### D6: Legacy series without future consuming occurrences are still marked

A legacy series of a limited organization whose compensation is consuming gets `is_quota_priced` and the fallback even when it currently has no selectable occurrences (for example all are before the limit's valid-from date), because the extension will create occurrences in limited years later. Series with a non-consuming compensation are not touched: the series compensation keeps pricing them, which equals the quota rule.

### D7: Report

`TransitionReport` is a dataclass per organization: allowance and remaining per year before the run, lists of kept-free, charged (with compensation and amount), removed (deleted occurrences and cancelled bookings) and updated series. The command prints a summary line per organization and, at verbosity 2, every booking with date, resource and outcome. Totals follow at the end. The dry run prints the same report prefixed with "DRY RUN".

### D8: Idempotency

After a run, every selected booking is either flagged, priced with a non-consuming compensation, cancelled or deleted, and every legacy series is marked. A second run selects nothing. The command therefore needs no state and can be re-run after a partial failure.

## Risks / Trade-offs

- [The command runs while an organization is booking] → The lock on the organization row serializes it with `save_booking`, `save_booking_series` and the nightly extension.
- [Chronological allocation differs from the first-created rule used from then on] → Documented in the ADR and the announcement; applies only once, to bookings created before the rule.
- [Cheapest fallback may not be the one a manager would pick] → Visible in the report; a manager can change the fallback of a series in the admin, charged bookings can be edited to another compensation by the organization.
- [Cancelled standalone bookings without an automatic email] → The report lists them; managers inform the organizations. Expected to be rare.
- [Run before the grace period ends] → The dry run is the default suggestion in the README; the real run is a conscious second step.
- [Audit log without actor] → Management commands have no request user; the changes are logged with the command as context in the report output instead. Acceptable for a one-off.

## Migration Plan

1. Deploy; the command does nothing until it is invoked.
2. After the grace period: `python manage.py apply_free_bookings_quota --dry-run -v 2`, review the report, tell the few affected organizations.
3. `python manage.py apply_free_bookings_quota` (optionally `--organizations slug ...` to go in batches).
4. Rollback: there is none by design; the changes are the intended state. Charged bookings can be edited or cancelled by the organization, series fallbacks can be changed in the admin.

## Open Questions

None. The grace period length and the date of the run are decided by the board, not by the code.
