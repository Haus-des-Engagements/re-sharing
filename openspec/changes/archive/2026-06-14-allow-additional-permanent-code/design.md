## Context

Organization permanent codes are managed from `/organizations/manage-organizations/` via `manager_permanent_code_action_view` (`@manager_required`), which delegates to three service functions in `re_sharing/resources/services_permanent_code.py`: create, invalidate, renew.

Today, creating a code is blocked in two independent places when an active code exists:

1. **Service guard** — `create_permanent_code_for_organization` queries for an active code (`validity_start <= now` and `validity_end` null-or-future) and raises `ValidationError` if one is found.
2. **UI gate** — `manager_list_organizations.html` only renders the "Create Code" action inside the `{% if not organization.active_codes %}` branch; when codes exist it shows only Invalidate/Renew.

The `PermanentCode` model has no uniqueness constraint on organization, and the `renew` flow already produces two concurrently-active codes (old code valid for one more week). So multiple active codes per organization is an already-supported, already-handled state — the create block is artificial.

## Goals / Non-Goals

**Goals:**
- Let a manager add an additional permanent code while existing codes stay valid.
- Keep the existing `@manager_required` permission gate.
- Warn the manager in the confirm dialog when an active code already exists.

**Non-Goals:**
- No change to invalidate or renew behavior.
- No model or migration changes.
- No change to which accesses are assigned (`[1, 2, 8]`) or the code-generation algorithm.
- No new permission tier (staff/admin-only path was considered and rejected).

## Decisions

**Remove the service-level active-code guard rather than add a `force` flag.**
The guard at `services_permanent_code.py:46-58` is deleted so `create_permanent_code_for_organization` always creates. A `force=True` opt-in parameter was considered but rejected: the only caller is the create action, and the desired behavior is now "always allow," so a flag would be dead configuration. The active-code lookup (and its `Q`/`timezone` usage, if otherwise unused) is removed with it.

**Always render "Create Code" in the template, with a context-aware confirm.**
Move the create action out of the `{% if not organization.active_codes %}` exclusivity so it shows alongside Invalidate/Renew. When `organization.active_codes` is truthy, the `hx-confirm` text warns the organization already has an active code; otherwise it keeps the current "Create a new permanent code…" prompt.

**Keep `@manager_required`.**
Per the explore decision, any manager who can create/renew today can add an additional code. No new gate.

## Risks / Trade-offs

- **Accidental duplicate codes** → The warning confirm dialog when active codes exist makes the "additional" nature explicit, distinguishing it from Renew.
- **A second create email fires** → Consistent with the existing create flow (`send_permanent_code_created_email`); acceptable and expected.
- **Name collision** → New code reuses the `"Permanent code for {org}"` name; `name` is not unique, so this is harmless.
