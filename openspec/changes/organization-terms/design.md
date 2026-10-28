## Context

The public legal page lists eleven documents: values, privacy policy, platform terms, room terms, internet terms, lending terms, and house rules and fire safety for each location. Today `Organization` stores `values_approval` (boolean), `usage_agreement` (FileField, private storage) and `usage_agreement_date`; the creation form requires all three, the show page and the manager list display the upload. Nothing records versions or who accepted what.

Booking flows go through a session-backed form: `create_booking_data_form_view` stores the booking data and redirects to `preview_and_save_booking_view` or `preview_and_save_booking_series_view`; item lending has `preview_item_booking_view`. These three previews are the natural gate, because the user's input survives a detour.

The stakeholder wants one signed document at registration as a deliberate barrier and click acceptance everywhere else. Internet terms count as global terms and belong to registration.

Constraints: HackSoft style, coverage above 95 percent, minimal relations between apps (ADR 9; the `terms` app points at `Organization`, `User` and `Location`), private storage for uploads (ADR 20).

## Goals / Non-Goals

**Goals:**

- Know which version of which document each organization accepted, when and by whom.
- Ask at the moment a document matters, never earlier, and never twice for the same version.
- Let staff publish a new version and decide whether it needs re-acceptance, without a deploy.
- Keep registration to one signature plus one click.

**Non-Goals:**

- See the proposal. Additionally: per-user acceptance (acceptance belongs to the organization), and gating manager actions.

## Decisions

### D1: The registration document is renamed, not replaced

`usage_agreement` becomes `registration_document` and `usage_agreement_date` becomes `registration_document_date` through `RenameField`; files stay where they are, new uploads are named `_registration_document`. The form label links to the current version of the signed registration document (D2) when one is configured. `values_approval` is removed from the model in the same migration; nothing depends on it except the form, the admin, two templates and tests. Existing organizations therefore hold their old room agreement as registration document, which the stakeholder accepts. The existing values document is signed as is. `document-signing` later offers signing it online behind the same two fields.

Alternative: a new `signed_document` field with a data copy. Rejected, a rename says the same thing with no data movement.

### D2: Three models in a new `terms` app

`TermsDocument`: `name`, `slug`, `description`, `location` (nullable FK), `for_registration`, `for_room_booking`, `for_item_lending`, `requires_signature`, `is_active`, `order`. The three scope booleans replace a scope table; a document may carry several. `requires_signature` marks the document that is signed at registration instead of clicked; `clean()` allows it only together with `for_registration` and at most one active document may carry it. Documents with no scope are allowed; `organization-agreements` points at such documents as contract templates.

`TermsVersion`: `document`, `label`, `file` (public media, PDF validated) or `url`, `published_on`, `change_summary`, `requires_reacceptance`. A version of a document with `requires_signature` or without scopes must have a file, because it is the source PDF for signing. The current version of a document is its latest version with `published_on` not after today. Versions are never edited after publication; a correction is a new version.

`TermsAcceptance`: `organization`, `version`, `user`, `accepted_at`. Unique on (`organization`, `version`). Signing the registration document counts as acceptance and is recorded the same way by `create_organization`.

Alternative: a scope table with rows per scope. Rejected, three booleans say the same with one model less and no validation of scope rows.

### D3: The missing-terms selector

`missing_terms_versions(organization, scope, *, location=None)` returns the current versions the organization must accept: for every active document that carries the given scope or `for_registration`, and a location of none or the given one, the current version is missing when the organization accepted no version of the document at all, or when a version with `requires_reacceptance` was published after the latest version the organization accepted. A version without the flag never makes anything missing. Documents without a current version and documents with `requires_signature` are skipped: the signed document is never re-asked.

Registration documents are included at every gate, so a new privacy policy with the re-acceptance flag is asked at the next booking, and only that document.

### D4: One gate, three call sites

`require_terms(request, organization, scope, *, location=None)` returns `None` or a redirect to the interstitial with the scope, location and `next` in the query string. The interstitial view loads the missing versions, shows each with its link and a checkbox, and on submit stores one acceptance per version and redirects to `next`.

Call sites: the two room previews with scope room booking and the booking's location, and the item preview with scope item lending. The gate runs on GET and POST, before any save, so the session-held booking data survives the detour. `next` is validated with `url_has_allowed_host_and_scheme`.

### D5: Registration

The creation form renders one required checkbox naming every active registration document that is clicked, each with a link to its current version, plus the signed upload and date. `create_organization` stores an acceptance for each registration document's current version with the creating user, the signed one included. Without registration documents in the database the form shows no checkbox, which keeps existing tests meaningful and the rollout order free.

One checkbox for several documents is the usual pattern and still records one acceptance per document, so a later change to one document re-asks only that one.

### D6: Publishing and announcing

Versions are created in the admin. An admin action "Announce to organization admins" enqueues one email per confirmed organization naming the document, the change summary and whether re-acceptance is needed. No automatic email on publication.

### D7: Visibility

The organization show page lists the organization's acceptances. The admin registers all three models, acceptances filterable by organization and document, read-only. No manager list column: the interstitial is one click and the admin answers audit questions.

## Risks / Trade-offs

- [Existing organizations hit an interstitial at their next booking] → One page, one click per document, with the booking data preserved. Expected and accepted.
- [Several documents at once at a location's first booking] → Room terms, house rules and fire safety appear together; each gets its own checkbox and link.
- [Old registration documents are a different document than new ones] → The upload date tells them apart.
- [Privacy policy is not a contract] → It is listed as acknowledgement, with its own label, in the same mechanism.

## Migration Plan

1. Deploy the migration (rename, remove `values_approval`) and the new models.
2. Create the documents and first versions in the admin: values sheet with the registration scope and `requires_signature`; privacy, platform and internet terms with the registration scope; room terms with room booking; lending terms with item lending; house rules and fire safety per location with room booking.
3. Rollback: deactivate the documents; with no active documents the gates and the checkbox disappear, the rename stays.

## Open Questions

None.
