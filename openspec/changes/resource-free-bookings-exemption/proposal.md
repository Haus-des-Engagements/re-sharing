## Why

Whether a booking uses one of an organization's free bookings is decided only by its compensation. Some resources should never count, whatever compensation is chosen, for example a shared workspace that stays free without limit. Today this needs a second, unflagged free compensation per organization group for each such resource, and a resource added to the flagged compensation later counts without anyone deciding so.

## What Changes

- A resource gets a switch "exempt from free bookings", off by default, editable in the admin.
- A booking uses a free booking only when its compensation counts against free bookings **and** its resource is not exempt. On an exempt resource a flagged compensation behaves like an unflagged one: the booking is free, is not marked as using a free booking and is possible however many free bookings are left.
- The booking form on an exempt resource keeps offering the flagged compensation when the allowance is used up, shows no "remaining free bookings" hint and asks for no paid fallback on a series.
- The quota transition skips bookings and series on exempt resources. The custom email tags `bookings_above_limit`, `cost_above_limit` and `bookings_above_limit_without_rate` follow, because they come from the transition's dry run.
- Switching the exemption on or off affects only bookings priced afterwards. Bookings already marked as using a free booking keep that mark and still count as used.
- Out of scope: an exemption per location, an exemption per organization group and resource, and the manager's resource form (admin only, like the compensation flag).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `organization-free-bookings`: a resource can be exempt; a compensation consumes free bookings only when flagged and the resource is not exempt.
- `booking-free-bookings-pricing`: bookings, compensation choices and series on exempt resources are not priced against the allowance.
- `free-bookings-transition`: bookings and series on exempt resources are not selected.

## Impact

- `re_sharing/resources/models.py`: new boolean on `Resource`, with a migration.
- `re_sharing/resources/admin.py`: field, list column and filter on the resource admin.
- `re_sharing/bookings/services_pricing.py`: one shared check "does this booking consume a free booking", used by `price_booking` and `series_needs_fallback`.
- `re_sharing/bookings/services.py`: `_exceeds_free_bookings` and `save_booking` use the shared check.
- `re_sharing/resources/selectors.py`, `re_sharing/resources/views.py`, `re_sharing/templates/bookings/partials/compensations.html`: compensation choices, remaining hint and fallback selection on exempt resources.
- `re_sharing/bookings/services_quota_transition.py`: selection of legacy bookings and series.
- `docs/ADR/0027-...`: short record of the decision, extending ADR 0023.
- No dependency changes. No data migration: every resource starts as not exempt, so behaviour is unchanged until the switch is set.
