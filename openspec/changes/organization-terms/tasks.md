## 1. Registration document rename (red, then green)

- [ ] 1.1 Add a migration renaming `usage_agreement` to `registration_document` and `usage_agreement_date` to `registration_document_date` on `Organization` and removing `values_approval`; adjust the upload-to function's suffix; update factories, admin, show page, manager list and existing tests; a migration test asserts file and date survive
- [ ] 1.2 Update the creation and update forms and templates: the upload label links to the current version of the signed registration document when configured, no values checkbox; form tests for required upload, date and PDF validation

## 2. Terms models

- [ ] 2.1 Create the `terms` app (apps.py, admin, models, selectors, services, forms, views, urls, tests package, factories) and register it
- [ ] 2.2 Add `TermsDocument`, `TermsVersion`, `TermsAcceptance` as in design D2 with constraints and the PDF validator; add migration
- [ ] 2.3 Add factories and model tests: current version property with future dates, unique constraints, `clean()` allowing `requires_signature` only with `for_registration` and on one active document, file required on versions of signed and scopeless documents, `__str__`
- [ ] 2.4 Register the models in the admin: versions inline on the document, acceptances read-only with filters

## 3. Selector and acceptance service (red, then green)

- [ ] 3.1 Add tests for `missing_terms_versions(organization, scope, *, location=None)`: never accepted, accepted older without flag, accepted older with flag, accepted current, inactive document, no current version, location match and mismatch, registration documents included at every scope, signed document never included
- [ ] 3.2 Implement the selector with one query per call
- [ ] 3.3 Add tests and implementation for `accept_terms(user, organization, versions)`: acceptance rows with user and time, idempotent on repeat, foreign users denied

## 4. Gate and interstitial (red, then green)

- [ ] 4.1 Add tests for `require_terms(request, organization, scope, *, location=None)`: `None` when nothing is missing, redirect with scope, location and next otherwise
- [ ] 4.2 Add view tests for the interstitial: lists missing documents with links, checkbox per document, submit stores acceptances and redirects to next, unsafe next falls back to the organization page, nothing missing redirects immediately
- [ ] 4.3 Implement the gate helper, the interstitial view, template and url
- [ ] 4.4 Wire the gate into `preview_and_save_booking_view` and `preview_and_save_booking_series_view` (room booking scope, booking location) and `preview_item_booking_view` (item lending scope); view tests assert the detour keeps the session booking data and that no interstitial appears when nothing is missing

## 5. Registration integration (red, then green)

- [ ] 5.1 Add form tests: one required checkbox naming the clicked registration documents with links, none when no document has the registration scope, submission rejected when unchecked
- [ ] 5.2 Add service tests: `create_organization` records an acceptance per registration document with the creating user, the signed document included
- [ ] 5.3 Implement the checkbox and the acceptance recording

## 6. Announcements and visibility

- [ ] 6.1 Add the admin action "Announce to organization admins" with a `mails.py` task and template; tests for recipients, content and that creating a version sends nothing
- [ ] 6.2 Add the acceptances list to the organization page; view test
- [ ] 6.3 Translations for all new strings (`makemessages`, German translations)

## 7. Documentation and rollout

- [ ] 7.1 Add an ADR with the next free number, `Terms-Acceptance`, covering D1 to D5
- [ ] 7.2 Document the rollout from the design's migration plan in the README: documents, scopes and first versions to create
- [ ] 7.3 Run the full test suite with coverage and confirm it stays above 95 percent; run pre-commit on all changed files
