## 1. Signing module (red, then green)

- [ ] 1.1 Vendor `signature_pad` (pinned version) into `static/js/vendors/`
- [ ] 1.2 Add tests for the signature fields in `utils`: PNG data URL accepted, non-PNG and malformed base64 refused, over 200 KB refused, name and drawing required together, drawing together with an upload refused
- [ ] 1.3 Add tests for `append_signature_page`: page count of source plus one, source pages unchanged, the last page contains document name, party, name, function, account email and Europe/Berlin time; signing an already signed PDF adds one more page
- [ ] 1.4 Implement `re_sharing/utils/signing.py` with the form mixin and `append_signature_page`
- [ ] 1.5 Add the template partial with name field, pad, clear button and the confirmation sentence; make the pad work on phone width and refuse an empty pad in the browser

## 2. Agreement contracts (red, then green)

- [ ] 2.1 Add form tests: the application form and the signed document form show the signature fields only for kinds with a contract template, the signed document form only while the agreement is submitted; the manager forms never show them
- [ ] 2.2 Add service tests for `create_agreement` and `upload_signed_document` with a signature: the signed document is the prefilled contract followed by the signature page with the organization, the signer and `contact_person_function`, `signed_on` is today; applying without upload or signature still works; an upload replaces a document signed online
- [ ] 2.3 Implement the form and service changes and include the partial in the application and agreement templates; view tests for both paths

## 3. SEPA mandates (red, then green)

- [ ] 3.1 Add service tests for `create_mandate` and `upload_signed_mandate` with a signature: the signed document is the generated mandate with its reference followed by the signature page, the mandate is active, `signed_on` is today; an invalid IBAN creates nothing
- [ ] 3.2 Implement the form and service changes and include the partial in the mandate templates; view tests for both paths

## 4. Countersignature on approval (red, then green)

- [ ] 4.1 Add `AgreementKind.requires_countersignature` and `Manager.signatory_title`; add migrations; update admin and factories
- [ ] 4.2 Add tests for `approve_agreement` on a kind with the flag: refused without signatory title, refused without signature, on success the operator's signature page with the manager's name and title is appended to a contract signed online and to an uploaded one and all effects of approval happen; a failing approval leaves the document unchanged; kinds without the flag and rejection are unchanged
- [ ] 4.3 Implement the service change, the signature fields in the approval form for kinds with the flag, and the view; view tests for approval and refusals

## 5. Registration document (after `organization-terms`)

- [ ] 5.1 Add form tests: signature and function fields appear only when the registration document's current version has a file; exactly one of upload or signature
- [ ] 5.2 Add service tests for `create_organization` with a signature: the registration document is the version's PDF followed by the signature page with the organization's name and address, the date is today, terms acceptance and manager email as for an upload
- [ ] 5.3 Implement the form, service and template changes; view test

## 6. Documentation and rollout

- [ ] 6.1 Add an ADR with the next free number, `Electronic-Signatures`, covering D1 to D3 and D7 and the legal checks
- [ ] 6.2 Describe online signing and the countersignature in the manager guide for agreements
- [ ] 6.3 Translations for all new strings (`makemessages`, German translations)
- [ ] 6.4 Run the full test suite with coverage and confirm it stays above 95 percent; run pre-commit on all changed files
