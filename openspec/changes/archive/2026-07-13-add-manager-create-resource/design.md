## Context

The manager resource area (`re_sharing/resources/`) already implements list, show, edit, and compensation/image sub-views, all guarded by `@manager_required`. Creation is the missing operation — new resources can currently only be added via Django admin. The organizations app provides a close analog: `manager_list_organizations.html` renders a "New Organization" button in its heading that links to `create_organization_view`. We mirror that pattern for resources.

The `Resource` model uses `AutoSlugField(populate_from="name")`, so the slug is derived automatically and does not appear on the form. `ResourceEditForm` (a `ModelForm` over the 11 core fields) already works for both create and edit; its Submit label "Save" is acceptable on the create form.

## Goals / Non-Goals

**Goals:**
- Managers can create a resource from `/resources/manager/` and land on the new resource's detail page.
- Follow existing manager-view conventions (decorators, redirect targets, template structure).
- Keep creation logic in a service function per the project's Hacksoft styleguide.

**Non-Goals:**
- No changes to the `Resource` model, fields, or migrations.
- No changes to the edit view/template (a separate create template is used instead).
- No htmx partial for the create form (edit is a plain full-page form; match it).

## Decisions

- **Reuse `ResourceEditForm` as-is.** It already covers all core fields and validates identically for create. Alternative — a dedicated `ResourceCreateForm` — adds a near-duplicate class for no behavioral gain. The "Save" button is fine.

- **Dedicated `manager_create_resource.html` template.** The edit template hardcodes "Edit Resource", a resource-dependent breadcrumb, and assumes an existing `resource` in context. Branching it with conditionals would be messier than a small standalone template (breadcrumb: Manage Resources → New Resource; heading "New Resource"; `{% crispy form %}`).

- **`create_resource` service in `resources/services.py`.** Encapsulate `form.save()` behind a service function so the view stays thin and creation has a single call site, consistent with the styleguide. The edit view uses inline `form.save()`, but new code follows the service pattern.

- **URL ordering: register `manager/new/` before `manager/<slug:resource_slug>/`.** Django resolves patterns top-to-bottom; if the slug route came first, `new` would be captured as a `resource_slug` and route to the show view. Placing `manager/new/` immediately after `manager/` (and before the slug route) avoids this.

- **View contract mirrors `manager_edit_resource_view`.** `@require_http_methods(["GET", "POST"])` + `@manager_required`; GET renders a blank form, valid POST calls `create_resource` and redirects to `resources:manager-show-resource`, invalid POST re-renders with errors.

## Risks / Trade-offs

- **URL-ordering regression** → Covered by a test asserting `resources:manager-create-resource` reverses to `/resources/manager/new/` and that a GET returns the create form (not a 404 from the show view).
- **Slug collision on duplicate names** → `AutoSlugField` already de-duplicates slugs; no extra handling needed. Out of scope to change existing behavior.
