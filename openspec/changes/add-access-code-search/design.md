## Context

The code a caller reads out is derived at read time by `get_access_code()` (`re_sharing/resources/services.py:174`), not stored in one place:

1. `PermanentCode` for the booking's organization + the resource's access, valid at `timespan.lower` → that code
2. else the access (or its parent) has a `smartlock_id` → `booking.access_code`
3. else a general `PermanentCode` with `organization IS NULL` → that code
4. else `None`

`manager_filter_bookings_list` (`re_sharing/bookings/services.py:548`) already scopes the list to the manager's organizations and resources and applies status, resource, location, date and recurrence filters. The template posts the form over htmx into `#booking-list`.

Measured against a production dump (29,493 bookings, 2026-09-06; a SQL reimplementation of the branch logic agreed with the real `get_access_code()` on 300/300 sampled bookings):

| | |
|---|---|
| bookings with non-blank `access_code` | 17,989 |
| …that actually display it (branch 2) | 2,544 (14%) |
| …phantoms, never displayed | 15,445 (86%) |
| bookings with `access_code = ''` | 11,504 (39%) |
| shows a code, Sept 2025+ — permanent vs booking | 59.6% / 40.4% |
| bookings covered by one general permanent code | 2,804 |
| bookings per org permanent code | avg 74.5, max 1,077 |
| naive rows returned for a real booking code | avg 1.032, max 2 |
| verified rows returned for a real booking code | avg 1.005, max 2 |
| overlapping bookings sharing a code on one access | 0 |
| org-code / general-code shadowing pairs | 0 |

## Goals / Non-Goals

**Goals:**
- One search field that resolves either kind of code, since the caller cannot tell them apart.
- Never return a booking that does not actually display the searched code.
- Keep result sets small enough to read while someone waits on the phone.

**Non-Goals:**
- No change to code derivation, generation, or Nuki sync.
- No uniqueness constraint on `Booking.access_code`.
- No pagination redesign of the manager booking list.

## Decisions

**Verify candidates with `get_access_code()` rather than reimplementing precedence in SQL.**
A pure-SQL union is feasible — production has 0 shadowing pairs, so the precedence ambiguity I was concerned about does not currently occur. It is rejected anyway: phantoms outnumber real booking codes 6:1, so correctness rests entirely on the branch logic, and a second copy of it would silently drift the next time `get_access_code()` changes. The prefilter selects candidates (bookings whose `access_code` matches, plus bookings whose organization/access is covered by a matching `PermanentCode`), then each candidate is confirmed with `get_access_code(booking) == query`. Cost is bounded by the date window below; candidates are loaded with `select_related("resource__access__parent_access", "organization")`.

**An active code search neutralizes the status and past/recurring defaults.**
The page defaults to `status="1"` (PENDING) and `show_past_bookings=False`. A caller's booking is almost always CONFIRMED and may have started hours ago, so the defaults would return nothing and the feature would look broken. This was the one open question from exploration; it is settled by existing precedent rather than preference — `manager_list_organizations.html:151` already links into this page as `?organization_search=…&show_past_bookings=on&show_recurring_bookings=on&status=all`, so "a lookup relaxes the list defaults" is already the established behavior for this page. Explicit values in the querystring still win, so a manager can narrow afterwards.

**Default date window of −7 days to +90 days, with a visible escape.**
One general permanent code covers 2,804 bookings and an org code up to 1,077; rendering those is useless on a phone call, and the list has no pagination. When a code search is active and no explicit `from_date`/`until_date` is given, the window is applied server-side and the results header states it with a "show all dates" link that sets an explicit unbounded range. Server-side rather than prefilling the inputs, because the htmx target is `#booking-list` and the form is not re-rendered on a partial swap. The bounds are a starting point, not a derived constant.

**Exact match after `strip()`, minimum length 3.**
Booking codes are exactly 6 digits; permanent codes are free-text `CharField(256)`. `icontains` on 6 digits would be noisy, and with 11,504 blank codes an unguarded empty query would match a third of the table. Blank/whitespace input is treated as "no search", not as `access_code=""`.

**Render the Code column only while a code search is active.**
The column needs `get_access_code()` per row (~2 queries each). Adding that to every default page load would be a real regression for a column nobody asked for; during a code search the candidate set is already small and already verified.

**Order matched bookings by proximity to now.**
With max 2 rows for a booking code this is cosmetic there, but it matters for permanent-code searches returning dozens. It replaces `order_by("created")` only when a code search is active.

**Organization search matches permanent codes including expired ones.**
55% of permanent codes are already expired, and the bookings-side search cannot explain an expired code — it returns an empty list with no reason. The org page already displays codes and already links through to this booking list. The join needs `.distinct()`, since organizations hold multiple codes.

## Risks / Trade-offs

- **Verification query cost** → bounded by the date window and the manager's scope; `select_related` covers the access chain. If it ever bites, the candidate set can be capped before verification.
- **"Show all dates" on a general permanent code renders 2,804 rows** → an explicit, opt-in action, consistent with the page's existing unbounded rendering. Not worth a pagination redesign in this change.
- **Two search boxes on the bookings page** (organization, access code) → they compose as `AND`, which is the page's existing model; the code field is placed next to the organization field and labelled.
- **A caller's code matching nothing** → possible when the code is expired or belongs to another manager's scope. The empty state should say which searches were tried rather than render a bare empty table.
