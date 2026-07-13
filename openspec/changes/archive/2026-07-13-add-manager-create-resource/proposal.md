## Why

Managers can list, view, edit, and manage compensations/images for resources, but there is no way to create a new resource from the manager UI. Today a new resource can only be added through the Django admin. The manager resource area is otherwise feature-complete, so this closes an obvious workflow gap.

## What Changes

- Add a **"New Resource"** button in the heading of the manager resource list page (`/resources/manager/`), mirroring the existing "New Organization" button at `/organizations/manage-organizations/`.
- Add a new manager view `manager_create_resource_view` (GET renders an empty form, POST creates the resource) protected by `@manager_required`.
- Add a new URL `resources:manager-create-resource` at `manager/new/`, registered **before** the `manager/<slug:resource_slug>/` pattern.
- Add a `create_resource` service function in `resources/services.py` to encapsulate creation.
- Reuse the existing `ResourceEditForm` for input; add a dedicated `manager_create_resource.html` template.
- On success, redirect to the new resource's manager detail page (`resources:manager-show-resource`).

## Capabilities

### New Capabilities
- `manager-resource-management`: Manager-facing creation of resources, including the entry-point button, the create view/route, form handling, and the create service.

### Modified Capabilities
<!-- None: no existing spec covers manager resource management. -->

## Impact

- Code: `re_sharing/resources/urls.py`, `re_sharing/resources/views.py`, `re_sharing/resources/services.py`, `re_sharing/templates/resources/manager_list_resources.html`, new `re_sharing/templates/resources/manager_create_resource.html`, tests in `re_sharing/resources/tests/`.
- No data model, migration, or dependency changes; `ResourceEditForm` and the `Resource` model (auto-slug from `name`) are unchanged.
- Access is limited to managers via the existing `@manager_required` decorator.
