## Context

The public legal page lists eleven documents: values, privacy policy, platform terms, room terms, internet terms, lending terms, and house rules and fire safety for each location. Today `Organization` stores `values_approval` (boolean), `usage_agreement` (FileField, private storage) and `usage_agreement_date`; the creation form requires all three, the show page and the manager list display the upload. Nothing records versions or who accepted what.

Booking flows go through a session-backed form: `create_booking_data_form_view` stores the booking data and redirects to `preview_and_save_booking_view` or `preview_and_save_booking_series_view`; item lending has `preview_item_booking_view`. These three previews are the natural gate, because the user's input survives a detour. Agreement applications (`organization-agreements`) add a fourth gate.

The stakeholder wants one signed document at registration as a deliberate barrier, click acceptance everywhere else, and no double acceptance for members. Internet terms count as global terms and belong to registration.

Constraints: HackSoft style, coverage above 95 percent, one outward relation per app (ADR 9; the `agreements` app already points at `Organization`, `User`, `OrganizationGroup` and `Access` by its own design), private storage for uploads (ADR 20).

## Goals / Non-Goals

**Goals:**

- Know which version of which document each organization accepted, when and by whom.
- Ask at the moment a document matters, never earlier, and never twice for the same version.
- Let staff publish a new version and decide whether it needs re-acceptance, without a deploy.
- Keep registration to one signature plus two clicks.

**Non-Goals:**

- See the proposal. Additionally: per-user acceptance (acceptance belongs to the organization), and gating manager actions.

## Decisions

### D1: The registration document is renamed, not replaced

`usage_agreement` becomes `registration_document` and `usage_agreement_date` becomes `registration_document_date` through `RenameField`; files stay where they are, new uploads are named `_registration_document`. The form label links to the values sheet instead of the room agreement. `values_approval` is removed from the model in the same migration; nothing depends on it except the form and tests. Existing organizations therefore hold their old room agreement as registration document, which the stakeholder accepts. A new values sheet layout is deferred; the existing values document is signed as is. Should a digital signature be introduced later, it replaces the upload and date behind the same two fields.

Alternative: a new `signed_document` field with a data copy. Rejected, a rename says the same thing with no data movement.

### D2: Three models in `agreements`

`TermsDocument`: `name`, `slug`, `description`, `location` (nullable FK), `admin_only`, `is_active`, `order`.

`TermsScope`: `document`, `scope` (registration, room booking, item lending, agreement kind), `agreement_kind` (nullable FK, required for the kind scope). Unique on the three. A document with several scopes is one row per scope.

`TermsVersion`: `document`, `label`, `file` (public media, PDF validated) or `url`, `published_on`, `change_summary`, `requires_reacceptance`. The current version of a document is its latest version with `published_on` not after today. Versions are never edited after publication; a correction is a new version.

`TermsAcceptance`: `organization`, `version`, `user`, `accepted_at`. Unique on (`organization`, `version`).

Alternative: scopes as a multi-choice field. Rejected, the kind scope needs a foreign key.

### D3: The missing-terms selector

`missing_terms_versions(organization, scope, *, agreement_kind=None, location=None)` returns the current versions the organization must accept: for every active document with a matching scope row and a location of none or the given one, the current version is missing when the organization accepted no version of the document at all, or when a version with `requires_reacceptance` was published after the latest version the organization accepted. A version without the flag never makes anything missing. Documents without a current version are skipped.

### D4: One gate, four call sites

`require_terms(request, organization, scope, **kwargs)` returns `None` or a redirect to the interstitial with the scope, kind and `next` in the query string. The interstitial view loads the missing versions, shows each with its link and a checkbox, and on submit stores one acceptance per version and redirects to `next`. Admin-only documents are listed without a checkbox for a booker, with the names of the organization's admins to ask; the form cannot be submitted until an admin accepted them.

Call sites: the two room previews with scope room booking and the booking's location, the item preview with scope item lending, and the agreement application view with scope agreement kind. The gate runs on GET and POST, before any save, so the session-held booking data survives the detour. `next` is validated with `url_has_allowed_host_and_scheme`.

### D5: Registration

The creation form renders the registration-scoped documents as required checkboxes built from the database, plus the signed upload and date. `create_organization` stores an acceptance for each registration document's current version with the creating user. Without registration documents in the database the form shows no checkboxes, which keeps existing tests meaningful and the rollout order free.

### D6: Publishing and announcing

Versions are created in the admin. An admin action "Announce to organization admins" enqueues one email per confirmed organization naming the document, the change summary and whether re-acceptance is needed. No automatic email on publication.

### D7: Visibility

The manager organization list gets a column with the number of missing room booking documents per organization, computed by the selector in bulk. The organization show page lists the organization's acceptances. The admin registers all four models, acceptances filterable by organization and document, read-only.

### D8: Order of changes

The models live in `agreements`. If this change ships before `organization-agreements`, it creates the app with only these models; the kind scope and the application gate are added when the kinds exist. If it ships after, the app already exists. Either order works.

## Risks / Trade-offs

- [Existing organizations hit an interstitial at their next booking] → One page, one click per document, with the booking data preserved. Expected and accepted.
- [Several documents at once at a location's first booking] → Room terms, house rules and fire safety appear together; each gets its own checkbox and link.
- [Admin-only document blocks a booker] → The page names the admins to ask; `admin_only` is off by default and meant for few documents.
- [Old registration documents are a different document than new ones] → The upload date tells them apart; the manager list shows the date.
- [Privacy policy is not a contract] → It is listed as acknowledgement, with its own label, in the same mechanism.

## Migration Plan

1. Deploy the migration (rename, remove `values_approval`) and the new models.
2. Create the documents and first versions in the admin: privacy, platform and internet terms with the registration scope; room terms with room booking and every agreement kind; lending terms with item lending; house rules and fire safety per location with room booking.
3. Replace the linked PDF on the registration form by the values sheet.
4. Rollback: remove the scope rows; with no active documents the gates and checkboxes disappear, the rename stays.

## Open Questions

- Whether and when a digital signature replaces the uploaded values sheet. Deferred together with the sheet's layout.
