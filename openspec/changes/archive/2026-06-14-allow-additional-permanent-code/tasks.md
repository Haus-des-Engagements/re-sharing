## 1. Tests (red)

- [x] 1.1 Rewrite `test_create_permanent_code_fails_when_active_code_exists` in `re_sharing/organizations/tests/test_views_permanent_code.py` to assert that creating with an active code present succeeds (HTTP 200) and results in a second `PermanentCode` for the organization; rename it accordingly (e.g. `test_create_additional_permanent_code_when_active_code_exists`)
- [x] 1.2 Add a test asserting the "Create Code" action is present in the returned partial even when an active code exists
- [x] 1.3 Run the new tests and confirm they fail (red)

## 2. Service change (green)

- [x] 2.1 Remove the active-code guard (the `existing_code` lookup and `ValidationError` raise) from `create_permanent_code_for_organization` in `re_sharing/resources/services_permanent_code.py`
- [x] 2.2 Remove now-unused imports (`Q`, and `timezone` if no longer referenced) if applicable

## 3. UI change

- [x] 3.1 In `re_sharing/templates/organizations/manager_list_organizations.html`, move the "Create Code" action out of the `{% if not organization.active_codes %}` exclusivity so it always renders
- [x] 3.2 Make the create action's `hx-confirm` context-aware: warn that the organization already has an active code when `organization.active_codes` is truthy, otherwise keep the existing prompt

## 4. Custom name for new code

- [x] 4.1 Add an optional `name` parameter to `create_permanent_code_for_organization`; use it when non-blank, otherwise fall back to the default derived name
- [x] 4.2 Pass the posted `name` through in `manager_permanent_code_action_view`
- [x] 4.3 Replace the "Create Code" confirm with a modal containing an optional name input (and the active-code warning); submit via HTMX with the name
- [x] 4.4 Add service- and view-level tests for custom name and blank-name default

## 5. Verify

- [x] 5.1 Run the permanent-code view tests and confirm they pass (green)
- [x] 5.2 Run the full test suite and ensure no regressions
- [x] 5.3 Run pre-commit (Ruff, djLint) on the changed files
