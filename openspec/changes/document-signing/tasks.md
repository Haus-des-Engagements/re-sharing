## 1. Setup

- [ ] 1.1 Confirm `organization-terms` is merged: the `registration_document*` fields and the `terms` app with the signed registration document are the base of this change
- [ ] 1.2 Add `pyhanko`, `pypdf` and `reportlab` to the dependencies; vendor `signature_pad` (pinned version) into static files
- [ ] 1.3 Add settings `SIGNING_SEAL_P12_PATH` and `SIGNING_SEAL_P12_PASSPHRASE` (both optional) with env defaults; document them in the README and `.envs` templates
- [ ] 1.4 Create the `signing` app (apps.py, admin, models, selectors, services, forms, tests package, factories) and register it in `LOCAL_APPS`

## 2. Data model

- [ ] 2.1 Add `SignedDocument` and `Signature` as in design D3 with a unique constraint on (`signed_document`, `role`); add migration
- [ ] 2.2 Add factories, including a minimal valid PDF fixture and a PNG signature fixture
- [ ] 2.3 Add model tests: completion derived from signature count and `expected_signatures`, unique role, `__str__`
- [ ] 2.4 Register the models in the admin read-only, no delete permission; register signatures with auditlog

## 3. Signing input (red, then green)

- [ ] 3.1 Add tests for the signature image field: valid PNG data URL accepted, non-PNG refused, over 200 KB refused, fully transparent drawing refused, malformed base64 refused
- [ ] 3.2 Add tests for the signing form mixin: name, drawing and confirmation required; exactly one of upload or signature; length limits; confirmation text contains the organization name; function supplied by the caller
- [ ] 3.3 Implement the field and the mixin

## 4. PDF pipeline and service (red, then green)

- [ ] 4.1 Add tests for rendering the signature page: page count of source plus one, source pages byte-identical in content, text on the last page contains name, function, organization, document name, Europe/Berlin time and source hash; one empty slot rendered per further expected signature
- [ ] 4.2 Add tests for sealing with a throwaway certificate generated in a fixture: seal validates with pyHanko, covers the whole document, a byte modification fails validation
- [ ] 4.3 Add a test that without a configured certificate the PDF is returned unsealed and a warning is logged
- [ ] 4.4 Add tests for `sign_document(...)`: signed document and signature record with every field from the spec, `sha256_after` equals the hash of the returned bytes, complete and sealed for one expected signature, unsealed for two
- [ ] 4.5 Add tests for `add_signature(...)`: slot 2 filled by overlay with name, function and time, source pages and slot 1 unchanged, document complete and sealed, complete document refused, hash mismatch of `current_pdf` refused and logged
- [ ] 4.6 Implement the renderer, the overlay, the sealer, `sign_document` and `add_signature` in `signing/services.py`

## 5. Registration integration (red, then green)

- [ ] 5.1 Add `Organization.registration_document_record` (nullable `OneToOneField` to `SignedDocument`, `PROTECT`); add migration
- [ ] 5.2 Add form tests: the sign-online option appears only when the signed registration document has a current version with a file; exactly one of upload or signature required; both refused with a message; upload path unchanged; function field present
- [ ] 5.3 Add service tests for `create_organization` with online signing: registration document is the signed PDF, date is the signing date, signed document linked with the user as signer and the organization's name and address on the page, terms acceptance of the signed version recorded, manager email still enqueued; failure during signing rolls back the organization
- [ ] 5.4 Add view tests: IP address and user agent passed to the service, an invalid form creates no signed document and does not re-render the drawing
- [ ] 5.5 Implement the form changes, the service changes and the view metadata extraction
- [ ] 5.6 Update the creation template with the choice, the signature pad, clear button and the link to view the current version; make the pad work on phone width
- [ ] 5.7 Show "signed online by <name>, <time>" on the organization page and the manager list when a record is linked, with template tests for both displays

## 6. Agreement contracts and countersignature (after `organization-agreements`)

- [ ] 6.1 Add `AgreementKind.contract_document` (nullable FK to `terms.TermsDocument`, `PROTECT`) and `requires_countersignature`, `Agreement.signed_document_record`, `Manager.may_countersign` and `signatory_title` with `clean()` requiring a title when flagged; add migrations; update admin and factories
- [ ] 6.2 Add form tests for the application form and the signed document upload: sign-online only when the contract document has a current version with a file, exactly one of upload or signature, function taken from `contact_person_function`
- [ ] 6.3 Add service tests for signing a contract: key facts and document name with version label as in design D10, two expected signatures for countersigned kinds, one otherwise, `signed_document`, `signed_on` and record set; uploading a new document clears the record link; completeness of uploaded and signed documents
- [ ] 6.4 Add tests for `countersign_agreement`: refused without flag, out of scope, without applicant signature, without active mandate, when not submitted, for kinds without countersignature; on success complete and sealed document, agreement active with the signing date as decision date and the manager as deciding manager, all approval effects, decision email names the contract on the agreement page; failure in approval leaves nothing signed
- [ ] 6.5 Add tests for `approve_agreement`: refused with a pointer to countersigning for an incomplete record, allowed for uploaded contracts and for membership signed online
- [ ] 6.6 Implement the form changes, the contract signing in `create_agreement` and `upload_signed_document`, `countersign_agreement`, the approval message and the decision email wording
- [ ] 6.7 Add the countersign form and action on the manager agreement detail (shown only to flagged managers), the "awaiting countersignature" filter on the manager list, and the admin warning when amount or details differ from the signed key facts; view tests for every action and denial

## 7. SEPA mandates (after `organization-agreements`)

- [ ] 7.1 Add `SepaMandate.signed_document_record`; add migration
- [ ] 7.2 Add tests for rendering the mandate page: standard mandate text, creditor name and identifier, mandate reference, account holder, IBAN, BIC, bank name, recurring payment
- [ ] 7.3 Add tests for `create_mandate` with online signing: reference generated before rendering and shown on the PDF, signed document and date set, record linked, function from the agreement, invalid IBAN signs nothing, no email enqueued
- [ ] 7.4 Implement the mandate renderer, the form choice and the service change

## 8. Documentation and rollout

- [ ] 8.1 Add an ADR with the next free number, `Electronic-Signatures`, covering D1, D2, D4, D5 and D11, including the legal checks for the follow-ups
- [ ] 8.2 Document the rollout from the design's migration plan in the README: creating the seal certificate, the terms documents and versions to prepare, configuring kinds, flagging the authorized manager, the privacy policy sentence
- [ ] 8.3 Translations for all new strings (`makemessages`, German translations)
- [ ] 8.4 Run the full test suite with coverage and confirm it stays above 95 percent; run pre-commit on all changed files
