## Why

Managers currently have only two ways to take an organization out of service: leave it `Pending` or `Reject`/cancel it. Rejection is a moral block (the organization is not allowed to book), but managers also need a neutral, reversible "off switch" for organizations that are simply not currently active — without implying any wrongdoing — and the ability to re-activate them later so they can book again.

## What Changes

- Add a new reversible organization status **Deactivated**, distinct from the morally-loaded **Rejected** state.
- Managers can **deactivate** a `Confirmed` organization (`Confirmed → Deactivated`) and **activate** it again (`Deactivated → Confirmed`).
- A deactivated organization cannot create bookings (the existing booking gate already blocks any non-`Confirmed` status).
- No emails are sent on deactivate or activate (unlike the existing confirm/cancel flows).
- Clean up the status enum conflation: organization status logic uses `Organization.Status` everywhere instead of borrowing values from `BookingStatus`. The existing **Rejected** wording is kept.

## Capabilities

### New Capabilities
- `organization-lifecycle`: The set of organization statuses (Pending, Confirmed, Rejected, Deactivated), the manager-driven transitions between them, and how status gates booking.

### Modified Capabilities
<!-- None: organization status behavior is not yet captured in an existing spec. -->

## Impact

- `re_sharing/organizations/models.py`: add `Status.DEACTIVATED`; add `is_deactivatable()` / `is_activatable()` helpers; switch `is_cancelable()` / `is_confirmable()` off `BookingStatus`.
- `re_sharing/organizations/services.py`: new `manager_deactivate_organization` / `manager_activate_organization`; replace `BookingStatus` references with `Organization.Status`.
- `re_sharing/organizations/views.py` + `urls.py`: two new manager PATCH endpoints mirroring cancel/confirm.
- `re_sharing/templates/organizations/manager_list_organizations.html`: Deactivate / Activate dropdown actions and a status badge colour for the new state.
- New migration for the `Status` choices change (no data migration; existing values keep their meaning).
- Tests for transitions, the booking gate, and view permissions.
