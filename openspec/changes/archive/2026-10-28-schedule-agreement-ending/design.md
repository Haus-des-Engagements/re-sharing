## Context

`end_agreement(user, agreement, end_date=None)` sets `end_date = agreement.end_date or end_date or today`, then ends at once: status `Ended`, group removed, code validity capped, later collections cancelled, deposit refund recorded, email enqueued. The manager's "End agreement" form passes its optional date straight through. `end_expired_agreements` runs nightly and ends active agreements whose end date is before today. `next_billing_periods` already stops at the end date, so no collection is created for a period starting after it; collections created before the date was set (up to `COLLECTION_LOOKAHEAD_DAYS` ahead) remain.

## Goals / Non-Goals

**Goals:** the group, code and access last until the end date; collections never run past it; the manager's date always wins.

**Non-Goals:** see the proposal.

## Decisions

### D1: The view decides between ending and scheduling

`manager_end_agreement_view` takes the form date, defaulting to today. A date after today calls `schedule_agreement_end`; otherwise `end_agreement` with that date. The services stay single-purpose and the daily command keeps calling `end_agreement(None, agreement)`.

### D2: `end_agreement` uses the given date first

`end_date = end_date or agreement.end_date or today`. The command passes no date and uses the stored one; a manager ending early overrides a later stored date. Immediate endings are allowed before the start date (withdrawn before it began); only scheduled dates must not precede the start.

### D3: `schedule_agreement_end`

Manager in scope, agreement `Active`, date after today and not before the start date. Saves `end_date` under `set_actor` and calls `_drop_collections_after(agreement)`. No email, no group or code change.

### D4: `_drop_collections_after(agreement)`

For collections with `period_start` after the end date: `Planned` ones are deleted, so moving the date later lets the daily job create them again; `Notified` ones are cancelled with a status note, since the organization already received the pre-notification. Collections in a run or later are left alone; a manager handles them by hand. `end_agreement` and `manager_update_agreement` (when the end date changed) use the same helper, replacing the cancel-only update in `end_agreement`.

### D5: Display

The agreement page shows "Ends on <date>" with a hint that the agreement stays active until then. The manager's end form is prefilled with the scheduled date and its button reads "Change end date" while an end is pending.

## Risks / Trade-offs

- [Date moved later after a notified collection was cancelled] → That period is not recreated (cancelled periods are never recreated); the manager collects it by hand. Rare, since notices are usually given well ahead of the lookahead window.
- [Ended email only on the actual end] → The organization gets no automatic confirmation of the notice; managers confirm by hand as today.

## Migration Plan

No migration. Agreements ended early in the past stay ended.

## Open Questions

None.
