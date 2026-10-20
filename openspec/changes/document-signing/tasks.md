## 1. Setup

- [ ] 1.1 Confirm `organization-terms` task 1 (rename to `registration_document*`) is merged; this change builds on those field names
- [ ] 1.2 Add `pyhanko`, `pypdf` and `reportlab` to the dependencies; vendor `signature_pad` (pinned version) into static files
- [ ] 1.3 Add settings `SIGNING_SEAL_P12_PATH`, `SIGNING_SEAL_P12_PASSPHRASE` (both optional) and `SIGNING_REGISTRATION_TEMPLATE_SLUG` (default `registration`) with env defaults; document them in the README and `.envs` templates
- [ ] 1.4 Create the `signing` app (apps.py, admin, models, selectors, services, forms, mails, tests package, factories) and register it in `LOCAL_APPS`

## 2. Data model

- [ ] 2.1 Add `SigningTemplate`, `SignedDocument` and `Signature` as in design D3, with the PDF validator and private storage on the template file and a unique constraint on (`signed_document`, `slot`); add migration
- [ ] 2.2 Add factories, including a minimal valid PDF fixture and a PNG signature fixture
- [ ] 2.3 Add model tests: completion derived from signature count and `expected_signatures`, unique slot, `__str__`, non-PDF template refused
- [ ] 2.4 Register the models in the admin: templates editable; signed documents and signatures read-only, no delete permission; register signatures with auditlog

## 3. Signing input (red, then green)

- [ ] 3.1 Add tests for the signature image field: valid PNG data URL accepted, non-PNG refused, over 200 KB refused, fully transparent drawing refused, malformed base64 refused
- [ ] 3.2 Add tests for the signing form mixin: name, function, drawing and confirmation required; length limits; confirmation text contains the organization name
- [ ] 3.3 Implement the field and the mixin

## 4. PDF pipeline and service (red, then green)

- [ ] 4.1 Add tests for rendering the signature page: page count of source plus one, source pages byte-identical in content, text on the last page contains name, function, organization, document name, Europe/Berlin time and source hash; one empty slot rendered per expected signature
- [ ] 4.2 Add tests for sealing with a throwaway certificate generated in a fixture: seal validates with pyHanko, covers the whole document, DocMDP allows later signing, an empty field `slot-2` exists when two signatures are expected, a byte modification fails validation
- [ ] 4.3 Add a test that without a configured certificate the PDF is returned unsealed and a warning is logged
- [ ] 4.4 Add tests for `sign_document(...)`: signed document and signature record with every field from the spec, `sha256_after` equals the hash of the returned bytes, complete for one expected signature, template hash recorded, `page_path` stored, notification enqueued on commit
- [ ] 4.5 Implement the renderer, the sealer and `sign_document` in `signing/services.py`

## 5. Signing notification

- [ ] 5.1 Add tests for `signed_document_notification_email`: recipient is the signer, no attachment, absolute link to `page_path`, document name in subject, translated
- [ ] 5.2 Implement the mail task and templates

## 6. Registration integration (red, then green)

- [ ] 6.1 Add `Organization.registration_signed_document` (nullable `OneToOneField` to `SignedDocument`, `PROTECT`); add migration
- [ ] 6.2 Add form tests: the sign-online option appears only with an active registration template; exactly one of upload or signature required; both refused with a message; upload path unchanged
- [ ] 6.3 Add service tests for `create_organization` with online signing: registration document is the signed PDF, date is today, signed document linked with the user as signer and the organization's name and address on the page, organization page as `page_path`, manager email still enqueued; failure during signing rolls back the organization
- [ ] 6.4 Add view tests: IP address and user agent passed to the service, an invalid form creates no signed document and does not re-render the drawing
- [ ] 6.5 Implement the form changes, the service changes and the view metadata extraction
- [ ] 6.6 Update the creation template with the choice, the signature pad, clear button and the link to view the template; make the pad work on phone width
- [ ] 6.7 Show "signed online by <name>, <time>" on the organization page and the manager list when a signed document is linked, with template tests for both displays

## 7. Second signatures (red, then green)

- [ ] 7.1 Add tests for `add_signature(...)`: slot 2 filled with name, function and time, first seal still validates, document complete, complete document refused, hash mismatch of `current_pdf` refused and logged, unsealed documents stay unsealed
- [ ] 7.2 Add tests that completing a document enqueues a notification without attachment to every earlier signer
- [ ] 7.3 Implement `add_signature` and extend the notification

## 8. Agreement contracts and countersignature (after `organization-agreements`)

- [ ] 8.1 Add `AgreementKind.contract_template` and `requires_countersignature`, `Agreement.signed_document_record`, `Manager.may_countersign` and `signatory_title` with `clean()` requiring a title when flagged; add migrations; update admin and factories
- [ ] 8.2 Add form tests for the application form and the signed document upload: sign-online only with an active contract template, exactly one of upload or signature
- [ ] 8.3 Add service tests for signing a contract: key facts as in design D10, two expected signatures for countersigned kinds, one otherwise, `signed_document`, `signed_on` and record set; uploading a new document clears the record link
- [ ] 8.4 Add tests for `countersign_agreement`: refused without flag, out of scope, without applicant signature, without active mandate, when not submitted, for kinds without countersignature; on success complete document, agreement active with decision date today and the manager as deciding manager, all approval effects; failure in approval leaves nothing signed
- [ ] 8.5 Add tests for `approve_agreement`: refused for a countersigned kind with an incomplete record, allowed for uploaded contracts and for membership signed online
- [ ] 8.6 Implement the form changes, the contract signing in `create_agreement` and `upload_signed_document`, `countersign_agreement`, and the approval rule
- [ ] 8.7 Add the countersign form and action on the manager agreement detail (shown only to flagged managers), the "awaiting countersignature" filter on the manager list, and the admin warning when amount or details differ from the signed key facts; the signed contract download on the agreement page for its admins and managers in scope; view tests for every action and denial, including download access

## 9. SEPA mandates (after `organization-agreements`)

- [ ] 9.1 Add `SepaMandate.signed_document_record`; add migration
- [ ] 9.2 Add tests for rendering the mandate page: standard mandate text, creditor name and identifier, mandate reference, account holder, IBAN, BIC, bank name, recurring payment
- [ ] 9.3 Add tests for `create_mandate` with online signing: reference generated before rendering and shown on the PDF, signed document and date set, record linked with the mandate page as `page_path`, invalid IBAN signs nothing, notification without attachment and without IBAN
- [ ] 9.4 Implement the mandate renderer, the form choice and the service change; add the download on the applicant's mandate page with a permission test

## 10. Documentation and rollout

- [ ] 10.1 Add ADR `0027-Electronic-Signatures.md` covering D1, D2, D4, D5 and D11, including the legal checks for the follow-ups
- [ ] 10.2 Document the rollout from the design's migration plan in the README: creating the seal certificate, uploading the templates, configuring kinds, flagging the authorized manager, the privacy policy sentence
- [ ] 10.3 Translations for all new strings (`makemessages`, German translations)
- [ ] 10.4 Run the full test suite with coverage and confirm it stays above 95 percent; run pre-commit on all changed files
