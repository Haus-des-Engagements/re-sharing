## Context

Organization status is stored on `Organization.status` as an `IntegerField` whose choices come from `Organization.Status` (`PENDING=1`, `CONFIRMED=2`, `REJECTED=3`). However, the manager confirm/cancel services and `create_organization` currently mutate the field using values from a *different* enum, `BookingStatus` (`PENDING=1`, `CONFIRMED=2`, `CANCELLED=3`, `UNAVAILABLE=4`). This only works because the integers happen to line up for 1–3. The model helpers `is_cancelable()` / `is_confirmable()` also reference `BookingStatus`.

Booking is gated in `re_sharing.bookings.services.is_bookable_by_organization`, which returns `False` when `organization.status != Organization.Status.CONFIRMED` — so any new non-confirmed status is blocked from booking automatically.

The manager UI lives in `templates/organizations/manager_list_organizations.html`, where a per-row dropdown shows Cancel / Confirm actions gated by `is_cancelable` / `is_confirmable`, wired via htmx PATCH to `manager-cancel-organization` / `manager-confirm-organization`.

## Goals / Non-Goals

**Goals:**
- Add a reversible `Deactivated` status (`Confirmed → Deactivated → Confirmed`).
- Block booking for deactivated organizations (achieved for free via the existing gate).
- Untangle the enum conflation so organization status logic uses `Organization.Status` exclusively.
- Keep the existing "Rejected" wording for the moral-block state.

**Non-Goals:**
- Renaming `Rejected` or changing its meaning/value.
- Allowing `activate` to recover a `Rejected` organization.
- Sending emails on deactivate/activate.
- Touching `BookingStatus` usages that legitimately concern *Booking* status (selectors, admin booking filters, management commands).

## Decisions

- **New status value `DEACTIVATED = 4`.** Next free integer; does not collide with any existing `Organization.status` data. `BookingStatus.UNAVAILABLE` also equals 4, but the two enums are being decoupled, so the coincidence is irrelevant. Alternative considered: a separate boolean `is_active` field — rejected because it would create two overlapping sources of truth with `status` and complicate the booking gate.

- **Activate reuses the `Confirmed` target rather than a dedicated value.** "Activated" means "approved and able to book", which is exactly `Confirmed`. Keeps the state machine small and the booking gate unchanged.

- **Transitions restricted by dedicated helpers.** Add `is_deactivatable()` (`status == CONFIRMED`) and `is_activatable()` (`status == DEACTIVATED`), mirroring the existing `is_cancelable` / `is_confirmable` pattern. Services validate the guard and raise `InvalidOrganizationOperationError` otherwise, exactly like the cancel/confirm services.

- **Enum cleanup limited to organization-status sites.** Replace `BookingStatus` with `Organization.Status` only in `services.py` (`create_organization`, `manager_cancel_organization`, `manager_confirm_organization`) and `models.py` (`is_cancelable`, `is_confirmable`). The cancel path keeps writing value 3 — now as `Organization.Status.REJECTED` instead of `BookingStatus.CANCELLED` — so behaviour and stored data are unchanged.

- **No-op-ish migration for choices.** Adding a choice generates a Django `AlterField` migration; it does not alter stored data. No data migration needed.

- **Badge colour.** The status badge uses `text-bg-status-{{ organization.status }}`, so a `text-bg-status-4` style is needed for the new value to render with a colour.

## Risks / Trade-offs

- **Status filter dropdown** is populated from the `Status` choices; `Deactivated` will appear automatically as a filter option — desired, but verify the manager list view passes the full choices.
- **Existing rows with status 3** continue to display "Rejected"; the cleanup is purely internal (which enum constant is referenced), so there is no user-visible change to existing organizations. → Confirm no other code path reads org status via `BookingStatus`.
- **htmx row swap**: the new actions must target the same row partial as cancel/confirm so the dropdown re-renders with the updated available actions after a transition. → Reuse the existing `#tr-{slug}` target and `organization-item` partial.

## Migration Plan

1. Add `DEACTIVATED` to `Organization.Status`; generate the `AlterField` migration.
2. Ship model helpers, services, views, urls, template, and CSS together (trunk-based, single change).
3. Rollback: revert the change; the migration is a choices-only `AlterField` and is safe to reverse since no rows use value 4 unless the feature was exercised (and value 4 reverting to no-choice is harmless at the DB level).
