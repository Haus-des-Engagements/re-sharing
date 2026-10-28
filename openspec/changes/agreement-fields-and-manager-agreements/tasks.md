## 1. Prerequisite

- [x] 1.1 Archive the change `organization-agreements` so its specs are in `openspec/specs/` and the MODIFIED deltas of this change apply

## 2. Field definitions (red, then green)

- [x] 2.1 Add model tests for `AgreementKindField`: key unique per kind, reserved keys refused, choices required for choice fields only, minimum allowed for number fields only, ordering, `__str__`
- [x] 2.2 Add `AgreementKindField` (design D1) with `clean()`, migration `0002`, and a factory
- [x] 2.3 Add the data migration `0003` that creates field definitions from `form_type` (design D4), with a migration test for a coworking, office, cellar and membership kind
- [x] 2.4 Add migration `0004` dropping `AgreementKind.form_type` and remove `FormType` from the model

## 3. Form builder (red, then green)

- [x] 3.1 Add tests for `agreements/fields.py`: one form field per type with label, help text, required, minimum and choices; inactive fields skipped; order respected; stored values JSON-safe per type; a stored answer outside the choices stays selectable; `detail_items` shows active fields first, then other answers labelled by field label or key
- [x] 3.2 Implement `form_field_for`, `add_detail_fields`, `details_from` and move `detail_items` into `agreements/fields.py`
- [x] 3.3 Replace the four `ApplicationForm` subclasses and `APPLICATION_FORMS` by `ApplicationForm` using the builder; update `apply_view`, `create_agreement` and existing tests and factories that use `form_type`

## 4. Admin

- [x] 4.1 Add `AgreementKindField` as an ordered tabular inline on the kind admin; `key` read-only on existing rows; deleting a definition with answers refused with a message (design D3)
- [x] 4.2 Add `has_delete_permission` to the kind admin (no agreements) and the agreement admin (submitted, no collections)
- [x] 4.3 Add admin tests for the inline, the read-only key, the refused field deletion and both delete permissions

## 5. Manager services (red, then green)

- [x] 5.1 Add tests for `manager_create_agreement(user, organization, kind, form)`: scope, inactive kind, unconfirmed organization, duplicate refused, kinds closed for applications allowed, `Submitted` sends no email, `Active` records decision date and decider, adds a missing group, creates no code and no collections, and the daily job bills only periods due after creation
- [x] 5.2 Implement `manager_create_agreement` in `agreements/services.py`
- [x] 5.3 Add tests for `manager_update_agreement(user, agreement, form)`: scope, closed agreements refused, existing collections unchanged after an amount change, audit log entry with the manager as actor
- [x] 5.4 Implement `manager_update_agreement`
- [x] 5.5 Add tests for `delete_agreement(user, agreement)`: scope, only submitted without collections, mandates and stored PDFs removed after commit
- [x] 5.6 Implement `delete_agreement`

## 6. Manager views and templates

- [x] 6.1 Add `ManagerAgreementForm` (organization, status, decision date for active, core fields, detail fields, optional signed document, notes) and `ManagerAgreementEditForm` (core fields, detail fields, notes), both on the builder
- [x] 6.2 Add routes and views: `manage/new/` (kind choice), `manage/new/<kind>/` (create, `?organization=` preselects), `manage/<uuid>/edit/`, `manage/<uuid>/delete/` (confirmation, POST deletes)
- [x] 6.3 Add templates for the kind choice, the create and edit form and the delete confirmation; show edit and delete on the agreement page when allowed; add "New agreement" to the manager agreement list and the organization pages for managers
- [x] 6.4 Add view tests: non-manager and out-of-scope denied, create in both statuses, edit saves and refuses closed agreements, delete confirmation and refusal for active agreements, preselected organization

## 7. Wrap-up

- [x] 7.1 Add German translations for the new strings to `locale/de/LC_MESSAGES/django.po`
- [x] 7.2 Update the README rollout steps: set up each kind's application fields in the admin
- [x] 7.3 Run the full test suite and pre-commit on the changed files; coverage of the new code above 95 percent

## 8. Minimum amount per kind

- [x] 8.1 Add `AgreementKind.minimum_amount` (optional) with migration `0005`
- [x] 8.2 Enforce it in the application form with the minimum as hint; manager forms show the hint without enforcing it
- [x] 8.3 Tests for the form rule, the manager exception and the hint; German translations; README rollout note
