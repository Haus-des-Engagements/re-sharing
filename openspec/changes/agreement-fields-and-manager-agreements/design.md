## Context

The change `organization-agreements` added kinds as admin configuration, but the kind-specific application fields stayed in code: `AgreementKind.form_type` picks one of four `ApplicationForm` subclasses in `agreements/forms.py`, each listing `DETAIL_FIELDS` that are written into `Agreement.details` (JSON). The fields in use are few and simple: coworking asks for desks and hours per week (whole numbers, at least 1), office for a room (text), cellar for an area in m² (decimal, at least 1), membership for nothing.

Managers record decisions, end agreements and settle collections in the frontend, but creating an agreement for an existing member, or correcting one, is only possible in the Django admin (D10 of `organization-agreements`). The admin ignores manager scope and has no delete rule.

Neither change has been deployed. The `organization-agreements` change is implemented but not archived, so its requirements are not yet in `openspec/specs/`; it has to be archived before this change.

## Goals / Non-Goals

**Goals:**

- Staff configure a kind's application fields in the admin, without a deploy.
- One form builder serves the application, the manager's create and edit forms and the agreement page.
- Managers create, edit and delete agreements in the frontend, within their scope and with the same rules the services already enforce.

**Non-Goals:**

- See the proposal.

## Decisions

### D1: Field definitions are a child model of the kind

`AgreementKindField`: `kind` (FK, cascade), `key` (slug, unique per kind), `label`, `field_type` (`text`, `integer`, `decimal`, `date`, `choice`), `required`, `help_text`, `choices` (text, one choice per line, choice fields only), `min_value` (decimal, number fields only), `order`, `is_active`. Edited as a tabular inline on the kind admin. `clean()` requires choices for choice fields, forbids choices and minimums on types that do not use them, and forbids keys that collide with the core agreement fields (`start_date`, `amount`, …) so form field names never clash.

Alternative: a JSON schema field on the kind. Rejected, the admin has no usable editor for it and validation would be hand-written either way.

### D2: One form builder, answers keyed by field key

`agreements/fields.py` holds `form_field_for(definition)` (maps a definition to a Django form field), `add_detail_fields(form, kind, *, initial=None)` and `details_from(form, kind)`. `ApplicationForm` loses its subclasses and calls the builder for the kind's active fields in order. Stored values are JSON-safe: text and choice as string, integer as int, decimal as string, date as ISO string; `details_from` converts, and `detail_items(agreement)` converts back for display.

`detail_items` shows active fields in order, then answers of inactive or unknown keys after them, labelled with the definition's label or, without one, the key. Nothing an applicant entered disappears from the page.

### D3: Keys are stable once answered

The admin inline makes `key` read-only on existing rows and refuses deleting a definition while any agreement of the kind has that key in `details` (`details__has_key`). Staff deactivate the field instead. Labels, help texts, order, required and choices stay editable; a changed choice list does not alter stored answers, and the edit form offers a stored answer that is no longer a choice as an extra option so saving does not silently drop it.

### D4: Migrations

`0002` adds `AgreementKindField`. `0003` is a data migration that creates the definitions from each kind's `form_type` (coworking: `desks`, `hours_per_week`, integer, min 1; office: `room`, text; cellar: `area_m2`, decimal, min 1), keeping the existing keys so stored answers match. `0004` drops `form_type`. Reverse of `0003` is a no-op; the forms it came from are deleted in the same release.

### D5: Manager create in two steps

`/agreements/manage/new/` lists the active kinds within the manager's scope. `/agreements/manage/new/<kind>/` shows the agreement form for that kind: organization (confirmed organizations, sorted by name), status (`Submitted` or `Active`), the core fields, the kind's detail fields, optional signed document and notes. The kind decides which fields exist, so it is chosen first. The organization page and the manager organization list link to the first step for that organization (`?organization=<slug>` preselects it).

`services.manager_create_agreement(user, organization, kind, form, status)`:
- Refuses kinds out of scope (PermissionDenied), inactive kinds, unconfirmed organizations and an existing submitted or active agreement of the kind for the organization (same rule as applications). `accepting_applications` is ignored.
- `Submitted`: same record as an application, sends no application emails; the manager continues with mandate, approval and so on as usual.
- `Active`: for an existing agreement. Records `decided_at` (form field, defaults to today) and `decided_by`, adds the kind's group when the organization lacks it, creates no code, no deposit or first-period collection and sends no email. The daily job bills from the next full period that is due after the agreement was created, as for admin-entered agreements.

Alternative: create always as `Submitted` and approve right after. Rejected, approval would create a first-period collection and a code for members who already pay and hold a code.

### D6: Manager edit

`/agreements/manage/<uuid>/edit/` for submitted and active agreements within scope. Editable: start date, end date, amount, deposit amount, contact person function, notes and the detail answers, with the same validation as the application (required end date and deposit per kind, end after start). `services.manager_update_agreement` saves under `set_actor`, so auditlog records the change. Collections already created keep their amount, period and due date; a changed amount applies from the next collection the daily job creates. Changing a start date after approval does not recreate the first-period collection; a manager cancels or settles it by hand.

Status, kind and organization are not editable; the decision, end and delete actions cover the legitimate changes.

### D7: Delete only before anything happened

`services.delete_agreement(user, agreement)` refuses unless the agreement is `Submitted` and has no collections, then deletes its mandates and the agreement and removes their stored PDFs after commit. In practice a submitted agreement never has collections, since they start at approval, but the second check keeps the rule safe against admin-created data. A confirmation page at `/agreements/manage/<uuid>/delete/` names what is removed. `AgreementAdmin.has_delete_permission` and `AgreementKindAdmin.has_delete_permission` apply the same rules (kind: no agreements), so the admin cannot bypass them; `PROTECT` on `Agreement.kind` stays as the last guard.

### D8: Scope and visibility

All three actions use `manager_can_manage_kind` / `manager_can_manage_agreement`. The agreement page shows edit and delete to managers in scope when allowed. Organization admins keep their current rights; this change gives them nothing new.

## Risks / Trade-offs

- [A required field is added to a kind with existing agreements] → Only new applications and manager edits ask for it; editing an older agreement then requires an answer. Acceptable, the manager has the information.
- [Labels are free text in one language] → German labels, entered in the admin; the English UI shows them unchanged. Field types and validation messages stay translated.
- [Manager creates an active agreement for an organization that already pays on paper] → Same as the admin path: no collection before the agreement exists, first collection is the next full period.
- [Deleting removes stored PDFs] → Only for submitted agreements; the confirmation page lists the files, and auditlog keeps the deletion record.

## Migration Plan

1. Archive `organization-agreements` so its specs land in `openspec/specs/`.
2. Deploy with the migrations; existing kinds get their field definitions from `0003`.
3. README rollout: set up the kinds' fields in the admin instead of choosing an application form.
4. Rollback before any kind is edited: revert the release and migrate back to `0001`; `form_type` returns empty and must be set again in the admin.

## Open Questions

None.
