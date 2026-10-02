## Why

Today any organization in the default group can book most rooms free of charge without limit, because the free compensation is bookable for that group. From 2027 on, organizations that are not members (and are not self-help groups) should only get a fixed number of free bookings per calendar year (for example five), and pay the room's hourly rate beyond that. The code has no notion of "free", "member" or "quota" at all, so this cannot be configured; it needs a quota mechanism that is deployed well before 2027 so that bookings made in late 2026 for 2027 are already priced correctly.

Numbers from production (2026): about 140 organizations use the free compensation, about 65 of them more than five times a year, and 13 organizations make more than 26 free bookings a year. Nearly all heavy use comes from booking series, which are materialised up to two years ahead.

## What Changes

- Organization groups get an optional yearly free-bookings allowance and an optional date from which it applies. An organization's effective allowance is the most generous one across its groups; a group without a value means unlimited.
- Compensations get a flag marking them as consuming free bookings. Only the free room compensation gets it; other rate-less compensations (coworking, internal, individual) do not count.
- Every booking records whether it used a free booking. A booking counts as exactly one, regardless of its duration. The yearly counter of an organization is the number of its pending and confirmed bookings starting in that year that used a free booking. Cancelling a booking returns it to the allowance.
- Booking creation with a consuming compensation checks the remaining free bookings of the year of the booking's start date. If at least one is left, the booking is free and uses one. If none is left, the consuming compensation is not offered and the organization must choose a paid one; if the room has no paid compensation, the booking is not possible (existing behaviour when no compensation is available). There is no partial coverage.
- Each occurrence of a booking series counts as one booking and is priced individually, at creation and in the nightly extension, against the allowance of its own year. The user chooses a paid fallback compensation when selecting a consuming compensation on a room that has one and the allowance is limited on any occurrence date within the booking horizon, so a series starting in 2026 and running into 2027 gets a fallback too. Occurrences beyond the allowance are fully priced with it. Occurrences that can be neither covered by the allowance nor priced are not created, and the preview says so.
- Series created before this change are marked as not quota-priced and keep today's pricing in the nightly extension, so they do not lose dates before the transition tooling has handled them.
- Booking previews (single and series) and the compensation selector show how many free bookings are left and what will be charged. The user dashboard shows, per organization with a limited allowance, the used free bookings of the current and the following year.
- Booking edits re-check the allowance only when the organization, the compensation or the year of the start date changes, excluding the booking itself from the counter. Other edits (title, time, room) keep whether the booking is free, so bookings created before the quota can still be edited.
- The restriction starts through configuration, not through the deploy: the allowance applies from its valid-from date (2027-01-01) by booking start date, and nothing changes until the allowances and the compensation flag are set in the admin.
- Allocation is first created, first served. Existing bookings are never re-priced by this change.
- Auto-confirmation, manager permissions and the invoice flow are unchanged. Every booking is either fully free or fully paid, so invoice lines need no change. Managers booking for a limited organization follow the same quota rule; there is no manager bypass.
- Changing an allowance, its date or the compensation flag later affects only bookings priced afterwards.
- An ADR documents the quota model.

Out of scope, to be handled as follow-up changes:

- Transition of the already existing 2027 bookings of organizations that stay limited: one management command with a dry run, run once after the announcement grace period (see the migration plan in the design). Most affected organizations are expected to become members and thus unlimited.
- A manager overview of used free bookings per organization beyond the admin list filters.
- The coworking space weekday restriction, which is configured with the existing resource restrictions.

## Capabilities

### New Capabilities
- `organization-free-bookings`: yearly free-bookings allowance per organization group, effective allowance per organization, counting of used free bookings per calendar year.
- `booking-free-bookings-pricing`: how single bookings, booking edits and booking series occurrences are priced against the remaining free bookings, which compensations are offered, and what the user is told.

### Modified Capabilities

None. The existing specs (`organization-lifecycle`, `manager-resource-management`, `organization-permanent-codes`) keep their requirements.

## Impact

- `organizations`: new fields on `OrganizationGroup`, admin, factory, selectors for allowance and used free bookings.
- `resources`: new flag on `Compensation`, admin, factory, compensation selector view and partial.
- `dashboards`: used free bookings per organization on the user dashboard.
- `bookings`: new field on `Booking`, two new fields on `BookingSeries`, pricing service used by `generate_booking`, `create_booking_series_and_bookings`, `generate_bookings` and `extend_booking_series`; booking and series preview templates; server-side bookability check.
- Four schema migrations (the two `BookingSeries` fields share one) (no data migration; the flag and the allowances are set in the admin as part of the rollout).
- Docs: one ADR, README note on rollout configuration.
