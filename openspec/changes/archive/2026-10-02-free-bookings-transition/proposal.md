## Why

The free-bookings quota (ADR 0023) leaves bookings that existed before it was configured untouched: their `uses_free_booking` is false and series created before the quota keep today's pricing in the nightly extension. Organizations that stay limited therefore keep their existing 2027 series free on top of the new allowance, and those series extend free every night until someone intervenes. A small, auditable way to bring the remaining legacy bookings under the quota is needed once the announcement grace period is over. Most affected organizations are expected to become members, so the set to handle is small and does not justify a manager UI.

## What Changes

- A management command `apply_free_bookings_quota` with `--dry-run` and an optional list of organizations.
- For every organization whose allowance is limited, the command takes its future, not yet invoiced legacy bookings with a consuming compensation that start on or after the date its limit applies: single bookings and occurrences of series created before the quota.
- Per calendar year, the earliest of these bookings get the organization's remaining free bookings (chronological allocation, as none of them were created knowing the rule). The rest are charged with the cheapest paid hourly compensation the organization can book for the room. Where the room has no paid compensation, series occurrences are deleted and single bookings are cancelled.
- Legacy series of the organization with a consuming compensation get the chosen fallback and `is_quota_priced`, so the nightly extension prices their future occurrences from then on.
- The command prints a per-organization report (kept free, charged with amount, removed, series updated) that managers use to inform the organizations by hand. It sends no emails.
- A second run finds nothing left to do; the dry run performs the same work inside a transaction that is rolled back.

Out of scope:

- A manager page with preview and per-organization apply (decided against in the quota change).
- Automatic emails to the affected organizations.
- Re-pricing bookings that already happened or are invoiced.

## Capabilities

### New Capabilities
- `free-bookings-transition`: selection of legacy bookings of limited organizations, chronological allocation to the remaining allowance, fallback pricing or removal, marking of legacy series, dry run, report and idempotency of the transition command.

### Modified Capabilities

None. `organization-free-bookings` and `booking-free-bookings-pricing` keep their requirements; the command uses their selectors and pricing rules.

## Impact

- `bookings`: new service module for the transition, new management command, tests.
- `organizations`: selector for organizations with a limited allowance.
- Docs: README rollout section gains the command; ADR 0023 is unchanged (the transition is already described there as a follow-up).
- No schema migration.
