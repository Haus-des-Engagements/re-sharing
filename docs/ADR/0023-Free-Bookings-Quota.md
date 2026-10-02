# 0023. Free Bookings Quota

Date: 2026-10-02

## Status

Accepted

## Context

Pricing is data-driven: a `Compensation` carries an optional hourly rate and the organization groups that may pick it. The free room compensation has no rate and is bookable for the default group, so nearly every organization could book rooms free of charge without limit. Membership and self-help status are plain group tags with no effect on pricing.

From 2027 on, organizations that are neither members nor self-help groups get a fixed number of free bookings per calendar year and pay the room's hourly rate beyond that. Nearly all heavy free use comes from booking series, which are materialised up to two years ahead, so the mechanism had to be deployable in autumn 2026 without touching 2026 pricing while bookings made for 2027 are already priced correctly.

## Decision

### Allowance on organization groups, valid from a date

`OrganizationGroup.free_bookings_per_year` and `OrganizationGroup.free_bookings_valid_from` are set together or not at all (`clean()` and a check constraint). An organization's allowance for a booking is the most generous one across its groups for the booking's start date; a group without a number, or whose valid-from date lies after the start date, counts as unlimited. There is no member flag: member and self-help groups simply carry no number. The restriction therefore starts through configuration, not through a deploy.

Changing the number, the date or the compensation flag only affects bookings priced afterwards. No allowance history is kept; the counter is compared with the current allowance and the remaining count floors at zero.

### Consumption is flagged on the compensation

`Compensation.counts_against_free_bookings` marks the compensations that use a free booking. It cannot be set on a compensation with an hourly or daily rate. Other rate-less compensations (coworking, internal, individual) stay unflagged.

### A booking counts as one and stores that it did

`Booking.uses_free_booking` is set when a booking was priced against a limited allowance and a free booking was left. A booking counts as one whatever its duration. The used free bookings of a year are the organization's pending and confirmed bookings with the flag and a start date in that year; cancelling returns the free booking. A free booking keeps `total_amount` empty, as any compensation without a rate does.

Bookings that existed before the quota was configured stay unflagged and do not count. An organization that loses its unlimited group therefore starts with the full allowance on top of its existing free bookings.

### One pricing function

`price_booking` in `bookings/services_pricing.py` sets compensation, amount and flag on an unsaved booking: free while a free booking is left, otherwise charged with a fallback compensation for the full duration, otherwise `FreeBookingsExhaustedError`. There is no partial coverage. It is used by single bookings, booking edits, series creation, the nightly extension, the admin action and series confirmation.

The quota applies to managers as well; there is no manager bypass and no manual extra free booking.

### Edits are re-evaluated only when it matters

An edit is priced against the allowance only when the organization, the compensation or the calendar year of the start date changes, with the booking itself excluded from the count. Other edits keep whether the booking is free, so bookings created before the quota can still be edited. The compensation endpoint keeps the edited booking's compensation in the choices for the same reason.

### Series occurrences count individually

Each occurrence of a series counts as one booking and is priced against the allowance of its own year, in date order, at creation and in the nightly extension. A series with a consuming compensation names a `fallback_compensation` up front when the allowance is limited on any occurrence date within the booking horizon, which includes series starting in 2026 and running into 2027. Occurrences beyond the allowance are charged with the fallback at its rate at generation time; occurrences that can neither be free nor charged are not created. A series with a fallback may start in a year whose free bookings are used up.

`BookingSeries.is_quota_priced` separates new series from series created before the quota. The branch lives in `generate_bookings`, so series creation, the nightly extension and the admin action behave the same: series without the marker keep the series compensation and amount, so they do not lose dates before the transition tooling has handled them. Admin edits of a quota-priced series do not overwrite the per-occurrence pricing.

An unavailable occurrence of a quota-priced series that becomes free on confirmation is priced at that moment, or deleted if it cannot be priced.

### First created, first served, no re-pricing

Free bookings are allocated in creation order; a series created in November uses next year's allowance with its first occurrences. Existing bookings are never re-priced by the mechanism. Saving a booking or a series locks the organization row and prices again, so parallel requests cannot both take the last free booking; the nightly extension and the admin action run one transaction per series under the same lock.

## Consequences

- Deploying the change does nothing until the free compensation is flagged and allowances with a valid-from date are set in the admin.
- Rooms without a paid compensation become unbookable for a limited organization once its free bookings are used; open-ended series on such rooms only get the first occurrences of each year.
- Organizations see their used free bookings per year on the dashboard, in the compensation selector and in both previews.
- Series created before the quota keep today's pricing in the nightly extension until a separate transition command marks them as quota-priced.
