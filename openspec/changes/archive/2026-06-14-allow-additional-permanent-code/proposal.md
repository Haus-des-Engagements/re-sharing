## Why

Managers can create a permanent access code for an organization, but only when the organization has no active code — the service raises a `ValidationError` and the UI hides the "Create Code" action once a code exists. Managers sometimes need a second, parallel permanent code (e.g. handing a distinct code to a different group while the original stays valid). The data model already permits multiple active codes per organization, so this restriction is an artificial block rather than a constraint.

## What Changes

- Allow creating an additional permanent code for an organization at `/organizations/manage-organizations/` even when an active code already exists.
- Remove the service-level guard in `create_permanent_code_for_organization` that raises `ValidationError` when an active code is present.
- Always show the "Create Code" action in the organization manager list; when active codes already exist, the confirm dialog warns that the organization already has an active code before proceeding.
- Keep the `@manager_required` permission gate unchanged — the same managers who can create/renew today can add an additional code.
- Update tests: the existing "fails when an active code exists" test flips to assert the additional code is created; add coverage for the create action being available alongside active codes.
- No model or migration changes — the data model already supports multiple active codes per organization.

## Capabilities

### New Capabilities
- `organization-permanent-codes`: Manager-facing management of organization permanent access codes — creating, adding additional, invalidating, and renewing codes from the organization manager list.

### Modified Capabilities
<!-- No existing specs in openspec/specs/; this capability is introduced new. -->

## Impact

- `re_sharing/resources/services_permanent_code.py` — remove the active-code guard in `create_permanent_code_for_organization`.
- `re_sharing/templates/organizations/manager_list_organizations.html` — always render the "Create Code" action; add a warning confirm when active codes exist.
- `re_sharing/organizations/tests/test_views_permanent_code.py` — update `test_create_permanent_code_fails_when_active_code_exists` and add coverage for the create action with existing codes.
- No database migration. `@manager_required` gate and the invalidate/renew flows are unchanged.
