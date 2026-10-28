## Why

The kind-specific application fields are hard-coded in four form classes, so a new kind or a changed field needs a developer and a deploy. Managers can only enter or correct agreements in the Django admin, which bypasses the scope rules and the agreement pages they already use.

## What Changes

- Each agreement kind gets a list of application fields, edited in the admin as part of the kind: key, label, type (text, whole number, decimal, date, choice), required flag, help text, choices for choice fields, minimum for number fields, order and an active flag.
- The application form, the manager's create and edit form and the agreement page are built from that list. Answers stay in `Agreement.details`, keyed by the field key.
- **BREAKING** `AgreementKind.form_type` and the four form classes are removed. A data migration turns each existing kind's form type into field definitions (coworking: desks, hours per week; office: room; cellar: area in m²; membership: none).
- A field that has answers cannot be deleted and its key cannot be changed; it is deactivated instead. Answers of inactive fields stay visible on the agreement page.
- Managers within scope can create agreements in the frontend for a confirmed organization and any active kind in scope, whether or not the kind accepts applications. They choose between a submitted agreement, which then follows the normal decision flow, and an existing active agreement, which only adds the kind's group if it is missing.
- Managers within scope can edit submitted and active agreements: dates, amount, deposit, contact function, notes and the detail answers. Status, kind and organization are not editable. Already created collections keep their amounts and periods.
- Managers within scope can delete a submitted agreement without collections, together with its mandates and their stored files. Every other agreement is rejected or ended instead. The admin applies the same delete rule.
- Kinds stay editable only in the admin. A kind in use cannot be deleted; it is deactivated.

### Non-goals

- Managing kinds in the frontend.
- Organization admins editing or deleting their own applications.
- Recalculating existing collections after an edit.
- Field types beyond the five listed, such as a link to a room resource, file uploads or multi-select.
- Translated field labels. Labels are entered in one language.

## Capabilities

### New Capabilities
- `agreement-kind-fields`: field definitions per kind, how they render and validate, and how their answers are stored and shown.
- `manager-agreement-management`: creating, editing and deleting agreements in the frontend by managers.

### Modified Capabilities
- `organization-agreements` (introduced by the change `organization-agreements`, which must be archived first): kinds no longer name a form type, kind-specific details come from the kind's field definitions, and existing agreements can also be entered by managers in the frontend.

## Impact

- `re_sharing/agreements`: new `AgreementKindField` model with admin inline, migrations (add model, convert form types, drop `form_type`), a form built from field definitions replacing `APPLICATION_FORMS`, new manager views, templates and services, admin delete rule, tests and factories.
- `locale/de/LC_MESSAGES/django.po`: new strings.
- README rollout steps: the kinds' fields are set up in the admin instead of picking a form type.
