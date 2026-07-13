## 1. Tests (red)

- [x] 1.1 Add test: manager GET `resources:manager-create-resource` returns 200 and renders the create form
- [x] 1.2 Add test: manager POST with valid data creates a `Resource` and redirects to `resources:manager-show-resource`
- [x] 1.3 Add test: manager POST with invalid data creates no `Resource` and re-renders the form with errors
- [x] 1.4 Add test: non-manager is denied access (via `@manager_required`)
- [x] 1.5 Add test: `resources:manager-create-resource` reverses to `/resources/manager/new/` (guards URL ordering vs. the slug route)
- [x] 1.6 Run the new tests and confirm they fail

## 2. Implementation (green)

- [x] 2.1 Add `create_resource` service function to `re_sharing/resources/services.py`
- [x] 2.2 Add `manager_create_resource_view` to `re_sharing/resources/views.py` with `@require_http_methods(["GET", "POST"])` and `@manager_required`, reusing `ResourceEditForm`, calling `create_resource`, and redirecting to `resources:manager-show-resource`
- [x] 2.3 Register URL `manager/new/` in `re_sharing/resources/urls.py` as `manager-create-resource`, placed before the `manager/<slug:resource_slug>/` pattern
- [x] 2.4 Create `re_sharing/templates/resources/manager_create_resource.html` (breadcrumb Manage Resources → New Resource, heading "New Resource", `{% crispy form %}`)
- [x] 2.5 Add the "New Resource" button in the heading of `re_sharing/templates/resources/manager_list_resources.html`, mirroring the "New Organization" button

## 3. Verify

- [x] 3.1 Run the full resources test suite and confirm all tests pass
- [x] 3.2 Run pre-commit (ruff, django-upgrade, djLint) and fix any findings
