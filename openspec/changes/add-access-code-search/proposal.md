## Why

Support staff take phone calls from people standing at a door, and the access code is the fastest identifier the caller has. Nothing in the manager UI can resolve one today.

A cross-check against a production dump (29,493 bookings, 2026-09-06) shows a naive `filter(access_code=...)` would be wrong more often than right:

- The displayed code is derived by `get_access_code()` from three sources; only one of them is `Booking.access_code`.
- 17,989 bookings carry a non-blank `access_code`, but only **2,544 (14%)** actually display it. `access_code` has a `default=` generator, so every booking gets one whether or not it is ever shown — the other 15,445 are phantoms that a naive search would match confidently and wrongly.
- Permanent codes have overtaken per-booking codes: of bookings that show a code from Sept 2025 onward, **59.6% show a permanent code** vs 40.4% a booking code. All 318 permanent codes have `validity_start` in 2026, so the trend is one-directional. A naive search misses all of them.
- 11,504 bookings (39%) have `access_code = ''`.
- 174 of 318 permanent codes (55%) are already expired — "my code stopped working" is a likely call.

## What Changes

- New access-code search field at `/bookings/manage-bookings/`, alongside the existing organization search.
- Resolution is a SQL candidate prefilter (booking codes + permanent codes) followed by verification with `get_access_code()`, so only bookings that genuinely display the code are returned.
- Blank or whitespace-only input is a no-op, never a filter.
- An active code search neutralizes the status and past/recurring defaults, and applies a default date window with a visible "show all dates" escape.
- A "Code" column, rendered only while a code search is active.
- `/organizations/manage-organizations/` search additionally matches `PermanentCode.code`, including expired codes.

## Capabilities

### New Capabilities
- `access-code-search`: manager-facing lookup of bookings and organizations by access code.

### Modified Capabilities
<!-- None; no existing spec covers booking list filtering or organization search. -->

## Non-goals

- No change to `get_access_code()` precedence, to code generation, or to Nuki sync.
- No uniqueness constraint on `Booking.access_code` — production has 0 overlapping same-code bookings on the same access.
- No backfill of the 8,307 historical blank codes; all are in the past, 0 upcoming.
- No public or self-service code lookup — manager-only, scoped to the manager's own organizations and resources.
- No new page, route, or navigation entry.
- No pagination redesign of the manager booking list.

## Impact

- `re_sharing/bookings/services.py` — `manager_filter_bookings_list` gains an `access_code_search` argument and the prefilter/verify step.
- `re_sharing/bookings/views.py` — `manager_list_bookings_view` reads and passes the parameter, adjusts filter defaults.
- `re_sharing/templates/bookings/manager_list_bookings.html` — search input, Code column, date-window notice.
- `re_sharing/organizations/services.py` — `manager_filter_organizations_list` search matches permanent codes.
- `re_sharing/bookings/tests/`, `re_sharing/organizations/tests/` — new coverage.
- No model changes, no migration.
