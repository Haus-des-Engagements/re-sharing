## Why

Ending an agreement removes the organization group, caps the entrance code, cancels debits and sends the ended email at once, even when the manager enters a future end date. A member giving notice in October to the end of the year loses the member group in October. A date entered for an agreement that already has an end date is ignored.

## What Changes

- Ending with today or a past date ends the agreement immediately, as now.
- Ending with a future date only schedules it: the end date is saved, the agreement stays active with its group, code and collections up to that date, and the daily command ends it after the date, including the ended email.
- The date entered by the manager replaces an existing end date. A future date must not be before the start date; ending immediately stays possible before the start, for an agreement withdrawn before it began.
- Collections for periods starting after the scheduled end date are removed when the date is set: planned ones are deleted, so they can be created again if the date moves later; notified ones are cancelled.
- The agreement page shows a pending end and lets the manager change its date.
- Changing the end date in the manager's edit form has the same effect on collections.

### Non-goals

- Withdrawing a scheduled end. A manager moves the date instead; clearing it is a later change.
- Prorating the last period. A period starting on or before the end date is billed in full, as today.
- A confirmation email when an end is scheduled. The ended email is sent when the agreement actually ends.

## Capabilities

### New Capabilities

None.

### Modified Capabilities
- `organization-agreements`: the requirement "Ending an agreement" distinguishes immediate and scheduled endings.

## Impact

- `agreements/services.py`: `end_agreement` honours the given date, new `schedule_agreement_end`, shared removal of collections after the end date, also used by `manager_update_agreement`.
- `agreements/views.py`, `forms.py`, `show_agreement.html`: end form validation, scheduled-end display.
- Tests and German translations.
