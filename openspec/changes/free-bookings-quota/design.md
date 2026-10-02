## Context

Pricing today is entirely data-driven. A `Compensation` carries an optional hourly rate and the organization groups that may pick it. The free room compensation has no rate and is bookable for the default group, so nearly every organization can book rooms for free without limit. Membership and self-help status are separate group tags with no effect on pricing.

A booking freezes its `compensation` and `total_amount` at creation (`generate_booking`). Booking series copy their compensation and per-booking amount onto every occurrence, both at creation (`create_booking_series_and_bookings`) and in the nightly `extend_booking_series` command, which keeps occurrences materialised 730 days ahead. Compensation choices are rendered by an htmx endpoint (`resources:get-compensations`) and validated server-side in `is_bookable_by_organization`. Both single bookings and series go through a preview page before saving.

Constraints:

- Must be deployable in autumn 2026 without changing 2026 pricing, while bookings created for 2027 are already quota-priced.
- Existing bookings must never be re-priced by the mechanism itself (that is a separate, manager-driven transition).
- HackSoft style: business logic in services and selectors, thin views, factories and tests for every path, coverage above 95 percent.

## Goals / Non-Goals

**Goals:**

- Configurable yearly free-bookings allowance per organization group, with an effective-from date.
- Deterministic, auditable consumption: every booking states whether it used a free booking.
- Correct pricing for single bookings, edits, series creation and nightly series extension.
- Clear feedback in the compensation selector and both preview pages.
- No behavioural change for organizations whose effective allowance is unlimited.

**Non-Goals:**

- Re-pricing or migrating existing bookings.
- A quota dashboard for managers beyond the admin list filters; users see their used free bookings on their dashboard (D16).
- Changing confirmation rules, manager permissions, or the invoicing flow.
- Fair or chronological re-allocation of free bookings after the fact.
- Weighting bookings by duration or capping the duration of a free booking.

## Decisions

### D1: Allowance lives on `OrganizationGroup`, effective allowance is the maximum

`OrganizationGroup.free_bookings_per_year` (positive integer, nullable) and `OrganizationGroup.free_bookings_valid_from` (date, nullable). Either both are set or both are empty; a model `clean()` and a `CheckConstraint` enforce it, so a number can never apply without a start date and an admin cannot limit the current year by forgetting the date. An organization's allowance for a given booking date is computed over its groups: a group with a null value, or whose valid-from date is after the booking date, contributes "unlimited"; otherwise it contributes its number. The maximum wins, unlimited beats any number.

Why: this removes the need for a "member" flag. Member and self-help groups simply carry no value. It also matches the existing pattern where groups grant rights additively (auto-confirmed resources, bookable private resources, compensations). The valid-from date makes the rollout a configuration step rather than a New Year's Eve deploy.

Changing the number, the date or the flag later affects only bookings priced after the change. Bookings that already exist keep their `compensation`, `total_amount` and `uses_free_booking`; occurrences for later years that series have already materialised are not re-priced either. The counter is simply compared with the new allowance from then on, so lowering the number can leave a year with more used free bookings than allowed, and the remaining count floors at zero. No allowance history per year is kept.

Alternative considered: a boolean `is_member` on `Organization` plus a global setting for the allowance. Rejected because it duplicates what groups already express and needs a deploy to change the number.

Alternative considered: an allowance table with one row per group and year. Rejected because the first years need a single number and a per-year model would still not re-price already materialised occurrences.

### D2: Consumption is flagged on `Compensation`, not inferred

`Compensation.counts_against_free_bookings` (boolean, default false). Only compensations with this flag consume the allowance. The flag is rejected by `clean()` and a `CheckConstraint` when the compensation has an `hourly_rate` or a `daily_rate`: a consuming compensation is free by definition, and a flagged rate would be priced at nothing while a free booking is left and at the rate afterwards.

Why: several compensations have no rate but must not count (coworking, internal, individual). Inferring "free" from a missing rate would be wrong for them.

### D3: A booking counts as one, and records that it did

`Booking.uses_free_booking` (boolean, default false). Used free bookings of an organization in a year are the number of its bookings with this flag set, `start_date` in that calendar year and status pending or confirmed. Cancelled and unavailable bookings do not count, so cancelling returns the free booking without any extra logic. Series cancellation deletes future occurrences, which has the same effect.

A booking counts as one regardless of its duration. A one hour meeting and a full-day workshop each use one free booking.

Why a stored flag rather than inferring from the compensation: already existing 2027 bookings with the free compensation (mostly series occurrences) would otherwise count immediately after rollout and exhaust the allowance of many organizations before they book anything new. The stored flag defaults to false, so existing bookings count zero, and the counter does not change retroactively if a compensation's flag is edited later. It also stays auditable through the audit log.

The flag is only set when the organization's allowance was limited at pricing time. Bookings of an unlimited organization stay unflagged. When an organization later loses its unlimited group, its existing free bookings therefore do not count and it starts with the full allowance of every year on top of them, like an organization that existed before the quota. This is accepted: group changes are manager actions, and the alternative, flagging every consuming booking, would exhaust the allowance of such an organization the moment it changes groups.

Why count bookings instead of hours: it is the rule the board wants to communicate ("five free bookings a year"), and it removes partial coverage entirely. Every booking is either fully free or fully paid.

Alternative considered: counting hours (the previous version of this change). Rejected because the allowance is defined as a number of bookings, and hours required partial pricing, an automatic fallback for single bookings, decimal bookkeeping and odd invoice lines.

### D4: One pricing function, used everywhere a booking is priced

A service `price_booking(booking, compensation, fallback_compensation=None, exclude_booking=None)` in `bookings/services.py` sets `compensation`, `total_amount` and `uses_free_booking` on an unsaved booking:

```
allowance unlimited or compensation not consuming
    → existing behaviour, uses_free_booking = False
remaining >= 1
    → consuming compensation, total None, uses_free_booking = True
remaining == 0 and fallback given
    → fallback compensation, total = duration * rate,
      uses_free_booking = False
remaining == 0 and no fallback
    → not priceable (raise FreeBookingsExhaustedError)
```

`total_amount` stays `None` for a free booking, as it is today for every compensation without a rate, so free, unlimited and legacy bookings look the same to the invoice filters (`total_amount__gt=0`) and the templates.

Selectors in `organizations/selectors.py` provide `get_free_bookings_allowance(organization, on_date)`, `get_free_bookings_used(organization, year, exclude_booking=None)` and `get_remaining_free_bookings(organization, on_date, exclude_booking=None)`. "Unlimited" is represented by `None`.

`FreeBookingsExhaustedError` can surface in the single booking preview (GET and POST of `preview_and_save_booking_view`) when another booking used the last free booking after the form was submitted. The view catches it, shows a message that no free booking is left for that year and that another compensation has to be chosen, and redirects to the booking form with the session data kept. The series view does not need this: its occurrences are re-priced at save and fall back or drop (D6, D8).

A fallback is only passed for series occurrences (D6). Single bookings never get an automatic fallback: with no partial case, a single booking whose allowance is exhausted simply cannot use the consuming compensation, and the user picks a paid one in the form, which is today's pricing path.

Call sites: `generate_booking` (new and edit, see D12 for when an edit is re-evaluated), `create_booking_series_and_bookings` and `generate_bookings` (per occurrence, with the number of not-yet-saved free occurrences per year added to the counter), `extend_booking_series` (per occurrence, as bookings are created one night at a time).

Why: one function means one set of tests for the pricing rules and no drift between single and series bookings.

### D5: Server-side guard in `is_bookable_by_organization`

The existing bookability check additionally rejects a consuming compensation when the organization's remaining free bookings for the booking's year are zero. The htmx compensation endpoint hides a consuming compensation when nothing is left and shows the remaining free bookings next to it otherwise. Hiding is convenience; the service check is the rule.

The quota rule applies to managers too. `is_bookable_by_organization` returns early for managers today, before any resource or compensation check; the quota check moves in front of that return, so a manager booking on behalf of a limited organization is priced and rejected like the organization's own booking. Managers have no way to grant an extra free booking; the allowance is changed through the groups.

For edits, the check applies only when the edit is re-evaluated (D12), so an unchanged booking can always be edited. The compensation endpoint therefore receives the booking being edited (optional `booking` parameter next to `selected_compensation`). While the organization and the calendar year of the start date in the request equal those of that booking, its current compensation stays in the choices whatever the remaining count is, and the remaining count shown excludes the booking itself. Without this, the form would hide the compensation of a booking created before the quota and force a compensation change, which D12 rules out.

For series, the quota rule of the guard and of the endpoint depends on the fallback (D6):

- A paid fallback is available for the room and the organization: the consuming compensation is offered and accepted even when the year of the first occurrence is exhausted. Occurrences of exhausted years are priced with the fallback and later years use their own allowance. Rejecting on the first occurrence would make it impossible for such a series to ever use next year's allowance.
- No paid fallback is available: the check applies to the first occurrence, as for a single booking.

The endpoint knows that a series is requested from the repetition field of the form, which is part of the same htmx request.

### D6: Series keep the chosen compensation, occurrences are priced individually

Each occurrence counts as one booking. A weekly series with the consuming compensation and an allowance of five uses the allowance of a year within its first five occurrences of that year.

`BookingSeries.compensation` stays as the user's choice. A new nullable `BookingSeries.fallback_compensation` stores the paid compensation to use once the allowance of a year is exhausted. The series form requires a fallback selection when the chosen compensation is consuming, the organization's allowance is limited on any occurrence date within the booking horizon (730 days, see D11), and a paid hourly compensation bookable by the organization exists for the room. Fallback choices are limited to those compensations. Each occurrence is priced with D4 for its own year; `total_amount_per_booking` becomes informational (the amount of a fully paid occurrence).

Occurrences that are `UNAVAILABLE` (room already taken) are not priced against the allowance and do not use a free booking.

A fallback-priced occurrence uses the fallback's hourly rate at the time it is generated, so a later rate change applies to occurrences the nightly extension creates afterwards, while legacy series keep their frozen `total_amount_per_booking`. A fallback that is no longer usable when an occurrence is generated (inactive, or no longer bookable by the organization for the room) is treated as no fallback: the occurrence is dropped. A manager sees this in the series admin and can set another fallback.

Occurrences that cannot be priced (allowance exhausted, no fallback) are not created. The preview lists how many occurrences are free, how many are paid at which rate, and how many are dropped. In the nightly extension the same rule applies silently; the org sees the missing dates in its series overview.

Alternative considered: creating unpriceable occurrences as `UNAVAILABLE`. Rejected because that status means "the room is taken" in the rest of the system and on the display boards.

Alternative considered: counting a whole series as one booking. Rejected because nearly all heavy free use comes from series; a series-as-one rule would leave that use unlimited.

### D7: First created, first served

Free bookings are allocated in creation order. A series created in November 2026 uses the 2027 and 2028 allowance with its first occurrences of each year immediately. A later one-off booking in 2027 is paid. No re-allocation happens on cancellation beyond the free booking flowing back into the pool.

Why: any other rule would re-price existing bookings and collide with issued invoices. The announcement email will state this explicitly.

### D8: Concurrency guard

Saving a priced booking locks the organization row (`select_for_update`) inside the request transaction (`ATOMIC_REQUESTS` is on) and recomputes the price before saving, applying the same re-evaluation rule for edits (D12). Two simultaneous bookings from the same organization then serialize on the lock.

The same holds for series. `save_booking_series` has no bookability check today and only saves what the view generated. It now

1. checks `is_bookable_by_organization` for the series compensation (quota rule as in D5),
2. checks that a given fallback is active, has an hourly rate and is bookable by the organization for the room, and that a fallback is present when the form rule (D11) requires one, because the values come from the session and not from a validated form,
3. locks the organization row and prices the occurrences again in date order before saving them.

The nightly extension and the admin action run outside a request, so there is no surrounding transaction. They wrap each series in its own `transaction.atomic()` block and take the same lock on the organization row before pricing. A failure in one series then does not roll back the others.

### D9: Invoices

No change. A booking is either free (no invoice line, as today) or priced with a paid compensation for its full duration, which is exactly today's hourly line.

### D10: ADR

Add `docs/ADR/0023-Free-Bookings-Quota.md` describing D1 to D4, D6, D7 and D11 to D16, so the "no member flag, groups carry allowances, a booking counts as one" decision is findable.

### D11: Series that cross into the first limited year need a fallback

The rollout sets `free_bookings_valid_from` to 2027-01-01 while series are created in 2026. A weekly series starting in November 2026 has an unlimited first occurrence but limited occurrences from January 2027 on. If the fallback were only required when the first occurrence is limited, such a series would get no fallback and every 2027 occurrence after the fifth would be dropped.

The series form therefore asks whether the allowance is limited on any occurrence date between the first occurrence and the end of the booking horizon (today plus 730 days, or the series' last date if earlier). Because a group's allowance can only change from unlimited to limited as the date moves forward (D1), checking the last occurrence date inside that window is sufficient; the selector `is_free_bookings_allowance_limited_until(organization, last_date)` wraps this.

Occurrences before the valid-from date are unlimited and do not use a free booking; only the occurrences on or after it are counted.

### D12: Editing a booking only re-evaluates the allowance when it matters

Edits go through the full booking form and preview (`update_booking_view` → `generate_booking`), so an organization changing only the title of a booking would otherwise re-price it. For the 2027 bookings that already exist when the quota is configured (`uses_free_booking` false), this would suddenly use one of the five free bookings, or reject the edit if none is left.

An edit is re-evaluated against the allowance only when one of these changes: the organization, the compensation, or the calendar year of the start date. Otherwise the booking keeps its `uses_free_booking` value and its compensation, the bookability guard (D5) does not apply the quota rule, and `total_amount` is computed as today from the compensation's hourly rate and the new duration. When an edit is re-evaluated, the booking itself is excluded from the used count.

A change of room, time or duration within the same year therefore never changes whether a booking is free.

Alternative considered: always re-price and exclude the booking itself. Rejected because it penalises edits of bookings that were created before the quota existed.

### D13: Series created before the quota keep today's pricing in the nightly extension

Existing series have no `fallback_compensation`. The extension command creates exactly one day per night (today plus 731 days) and never retries a date it skipped. Once the quota is configured, an existing weekly series with the free compensation would get five free occurrences in 2028 and then silently lose every further date for good.

A new `BookingSeries.is_quota_priced` (boolean, default false) marks series whose occurrences are priced with D4. Series created through the new creation path set it to true. Occurrences are priced with D4 only for series with the marker; series without it keep today's behaviour (the series compensation and `total_amount_per_booking`, `uses_free_booking` false). The transition follow-up sets a fallback and the marker on existing series of affected organizations.

The branch on the marker lives inside `generate_bookings`, not in `extend_booking_series`. `generate_bookings` has three callers: series creation, the nightly extension and the "Generate bookings" action of the series admin. With the branch in the shared function, all three price a series the same way, and the admin action cannot quota-price a legacy series by accident. Series creation sets the marker on the unsaved series before it generates the occurrences.

Why a marker instead of "no fallback means legacy": a new series on a room without any paid compensation also has no fallback, and for that series dropping occurrences beyond the allowance is the intended rule (D6).

Why keep today's pricing rather than drop: dropped dates cannot be recovered by the extension, while legacy-priced occurrences can still be re-priced by the transition tooling.

### D14: An unavailable occurrence is priced when it becomes confirmed

Occurrences that are `UNAVAILABLE` are not priced (D6). `manager_confirm_booking_series` looks at every occurrence that is not cancelled, including unavailable ones, and confirms it when the room has become free in the meantime. Such an occurrence would be confirmed with the consuming compensation, free of charge and without using a free booking.

When the confirmation of a quota-priced series turns an `UNAVAILABLE` occurrence into `CONFIRMED`, the occurrence is priced with D4 first, with the series fallback, against the allowance of its own year, and in date order. If it cannot be priced (allowance exhausted, no fallback), it is deleted, which is the same outcome as not creating it (D6). Series without the marker keep today's behaviour.

The opposite direction needs no rule: a free occurrence that turns `UNAVAILABLE` on confirmation no longer counts, and its free booking returns to the allowance. Later occurrences that were already priced with the fallback stay paid (D7).

Alternative considered: never confirming unavailable occurrences. Rejected because it changes the confirmation of every series, also of organizations without a limit.

### D15: Admin edits of a series do not overwrite per-occurrence pricing

`BookingSeriesAdmin.save_model` copies `organization`, `user`, `compensation`, `total_amount` and `title` from the series onto all of its bookings on every save. For a quota-priced series this would reset the occurrences priced with the fallback to the series compensation and amount, including past and invoiced ones, while `uses_free_booking` stays as it was.

For series with `is_quota_priced` true, the admin copies only `organization`, `user` and `title`. `compensation`, `total_amount` and `uses_free_booking` of the occurrences are left alone. Series without the marker keep today's behaviour, where all occurrences share the series pricing anyway.

### D16: Used free bookings on the user dashboard

The dashboard (`dashboards:users_bookings_and_permissions`) lists the user's organizations. For every organization with a limited allowance, the row shows the used and available free bookings of the current year and of the following year, for example "2027: 3 of 5". The following year is shown because series use next year's allowance long before it starts, and the series preview alone does not tell the organization how many are left. Unlimited organizations show nothing. The numbers come from the selectors of D4 (`get_free_bookings_allowance`, `get_free_bookings_used`), gathered in `dashboards/services.py` next to the existing dashboard data, so the view stays thin.

## Risks / Trade-offs

- [Series eat next year's allowance long before the year starts] → Stated in the announcement email and in the series preview. The transition tooling follow-up handles today's existing series.
- [A booking counts as one regardless of length, so organizations may book longer slots to make the most of a free booking] → Accepted, decided: no maximum duration for free bookings. Rooms are already limited by opening hours and availability.
- [A short booking "wastes" a free booking] → Intended simplicity of the rule; the selector shows the remaining count before booking.
- [Rooms without a paid compensation become unbookable for limited organizations once the allowance is used] → This is intended and, with the second location staying quota-only, the expected case there: once a limited organization has used its free bookings, it cannot book those rooms for the rest of the year, and series occurrences beyond the allowance are dropped because no fallback exists. The series preview states the dropped occurrences.
- [Nightly extension silently drops occurrences] → Only for quota-priced series without a fallback (D13). The series overview shows the gap. A per-series note or email is a possible follow-up.
- [Series created before the quota stay free in the nightly extension until the transition runs] → Intended (D13); those occurrences are far in the future and are re-priced by the transition tooling. If the transition is delayed, they remain free, which is today's behaviour.
- [An organization that later loses its unlimited group has quota-priced series without a fallback] → Its series drop dates beyond the allowance in the extension. Rare; a manager can set a fallback in the admin.
- [Editing a booking to a different year changes its quota year] → Handled by excluding the booking itself and re-checking against the target year; the preview shows the result. Edits within the same year are not re-evaluated (D12).
- [Changing the organization of a quota-priced series in the admin moves its free occurrences to the other organization's counter without re-pricing them (D15)] → Rare manager action; the counter can end above the allowance, the remaining count floors at zero. Re-pricing is left to the manager.
- [An unavailable occurrence that becomes free on confirmation but cannot be priced is deleted (D14)] → Same outcome as an occurrence that was never created; only for quota-priced series without a fallback.
- [Lowering the allowance or moving the valid-from date later leaves already priced bookings as they are (D1)] → Intended; the counter floors at zero and new bookings follow the new value. Communicated in the admin help text.
- [A fallback compensation is deactivated or loses its group while a series runs] → Occurrences generated afterwards are dropped as if the series had no fallback (D6); a manager sets a new fallback in the admin. Deactivating a compensation that is a fallback of a running series is a manager decision, not something the system prevents.
- [An organization splits into several organizations to multiply its allowance] → Organizations need manager confirmation; the rollout checklist asks managers to look for this when confirming new organizations.
- [Admins forget to flag the free compensation or set the allowance] → Rollout checklist in tasks; with nothing configured the system behaves exactly as before, which is the safe default.

## Migration Plan

1. Deploy the schema migrations. Defaults keep current behaviour: no allowances, no consuming compensation, no booking marked as using a free booking.
2. In the admin: flag the free room compensation as consuming; set the allowance on the default group and any other group that should be limited, with valid-from 2027-01-01; leave member and self-help groups empty.
3. Create paid compensations for the rooms that should stay bookable beyond the allowance. The second location stays quota-only and gets none.
4. From that moment, bookings starting in 2027 are quota-priced while 2026 bookings stay free. The switch is the admin configuration, not the deploy: configure it when the announcement goes out.
5. Rollback: clear the allowance values or the compensation flag; existing bookings keep their stored prices either way.
6. Transition of legacy bookings (follow-up change): after the announcement, organizations have a few weeks to trim their own 2027 series through the existing cancel flow and to apply for membership. Most are expected to become members and thus unlimited, so the remaining set is small. For it, one management command `apply_free_bookings_quota` with `--dry-run` handles all limited organizations in one run: legacy consuming bookings on or after the valid-from date are allocated chronologically per year to the remaining allowance, the rest is priced with the cheapest paid compensation bookable by the organization for the room, deleted (series occurrences) or cancelled (single bookings) where none exists, series get `is_quota_priced` and that fallback, and the command prints a per-organization report that managers use to inform the few organizations by hand. No per-organization preview or apply view.
7. When confirming new organizations after the rollout, managers check whether an organization is being split only to multiply the allowance.

## Resolved Questions

- The allowance value (for example five bookings) stays a board decision and is only a number in the admin; no code depends on it.
- The "mit Mietvertrag" group is unlimited and keeps `free_bookings_per_year` empty, like the member and self-help groups.
- The second location stays quota-only and gets no paid compensations, with the consequences described in Risks.
- Free bookings need no maximum duration; a booking counts as one whatever its length.
- Managers follow the quota rule like everyone else; there is no manager bypass and no manual extra free booking.
- `free_bookings_valid_from` is required whenever `free_bookings_per_year` is set.
- A compensation with an hourly or daily rate cannot be flagged as consuming.
- A free booking keeps `total_amount` `None`, as today.
- Changes to the allowance, the date or the flag affect only bookings priced afterwards; no allowance history is kept.
- An organization that loses its unlimited group gets the full allowance on top of its existing, unflagged free bookings.
- Users see their used free bookings per organization on the dashboard; a manager overview stays out of scope.
- If the last free booking is taken between preview and save of a single booking, the user is sent back to the form with a message.
- Fallback-priced occurrences use the fallback's rate at generation time; an unusable fallback counts as no fallback.
- The transition of legacy bookings is one management command with a dry run, run once after the grace period, not a per-organization tool (Migration Plan step 6).
