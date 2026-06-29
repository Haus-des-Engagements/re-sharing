## 1. Model & enum cleanup

- [x] 1.1 Write failing tests for `is_deactivatable()` (true only when `Confirmed`) and `is_activatable()` (true only when `Deactivated`)
- [x] 1.2 Add `DEACTIVATED = 4, _("Deactivated")` to `Organization.Status`
- [x] 1.3 Add `is_deactivatable()` and `is_activatable()` helpers to `Organization`
- [x] 1.4 Switch `is_cancelable()` / `is_confirmable()` to reference `Organization.Status` instead of `BookingStatus`; remove the now-unneeded `BookingStatus` import if unused
- [x] 1.5 Generate the `AlterField` migration for the `Status` choices change

## 2. Services

- [x] 2.1 Write failing tests for `manager_deactivate_organization` (Confirmed → Deactivated, no email; rejects non-confirmed; permission denied for non-managers)
- [x] 2.2 Write failing tests for `manager_activate_organization` (Deactivated → Confirmed, no email; rejects non-deactivated; permission denied for non-managers)
- [x] 2.3 Implement `manager_deactivate_organization` guarded by `is_deactivatable()`, raising `InvalidOrganizationOperationError` otherwise
- [x] 2.4 Implement `manager_activate_organization` guarded by `is_activatable()`, raising `InvalidOrganizationOperationError` otherwise
- [x] 2.5 Replace `BookingStatus` references in `create_organization`, `manager_cancel_organization`, `manager_confirm_organization` with the equivalent `Organization.Status` values

## 3. Booking gate

- [x] 3.1 Write/extend a test asserting a `Deactivated` organization cannot create a booking (non-manager) while a `Confirmed` one passes the org-status gate
- [x] 3.2 Confirm `is_bookable_by_organization` already blocks `Deactivated` via `status != Organization.Status.CONFIRMED` (no code change expected)

## 4. Views & URLs

- [x] 4.1 Write failing tests for the deactivate and activate manager views (success, permission, wrong-status)
- [x] 4.2 Add `manager_deactivate_organization_view` and `manager_activate_organization_view` mirroring the cancel/confirm views (htmx PATCH, returns the row partial)
- [x] 4.3 Register `manager-deactivate-organization` and `manager-activate-organization` URLs
- [x] 4.4 Add URL resolution tests alongside the existing cancel/confirm URL tests

## 5. Template & styling

- [x] 5.1 Add Deactivate dropdown action (gated by `is_deactivatable`) and Activate action (gated by `is_activatable`) to `manager_list_organizations.html`, targeting the existing `#tr-{slug}` row partial
- [x] 5.2 Add a `text-bg-status-4` badge colour for the `Deactivated` status (class already present; shared neutral colour, comment updated)
- [x] 5.3 Verify the status filter dropdown includes `Deactivated` (fed by `Organization.Status.choices`)

## 6. Verification

- [x] 6.1 Run the full test suite and confirm coverage stays >=95% (new code fully covered; 2 pre-existing unrelated failures confirmed on clean tree)
- [x] 6.2 Run pre-commit (ruff, django-upgrade, djLint) and resolve any findings
- [x] 6.3 Manually verify the deactivate → activate round trip in the manager organization list
