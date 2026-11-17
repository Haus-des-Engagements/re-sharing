## Why

Signed documents reach re-sharing as uploads: users download a PDF, print it, sign, scan and upload it, or paste a picture of their signature onto it. Signing inside re-sharing keeps the moral weight of a signature and removes the printer. A scan is legally a simple electronic signature already, so a signature drawn in the browser is worth the same, and none of the documents requires more.

Since `agreement-documents`, the system produces the documents to sign itself: the contract prefilled from the kind's template and the generated SEPA mandate. This change lets users sign those in place instead of printing them.

## What Changes

- Wherever a signed PDF is uploaded today, the form also offers signing online: the user types their name and draws their signature. The upload stays as the alternative.
- The server appends one signature page to the document, showing the drawn signature, typed name, function, organization, time and the account that signed, and stores the result in the same file field an upload would fill. Nothing else is stored: no signature records, no hashes, no seal.
- **Agreement contracts:** for kinds with a contract template, the applicant signs the prefilled contract when applying or afterwards.
- **SEPA mandates:** the generated mandate is signed when the bank data is saved or afterwards from the mandate page.
- **Countersignature:** an agreement kind can require a countersignature. Approving such an agreement is then reserved to managers with a signatory title, who sign in the approval form; their signature page is appended to the stored contract, whether it was signed online or uploaded.
- **Registration document:** after `organization-terms`, the creation form offers signing the registration document's current version online.
- ADR on the signature level: simple electronic signature, why the document itself is enough evidence, and when a qualified signature would be needed.

### Non-goals

- Advanced or qualified electronic signatures, identity verification, third-party signing services.
- Tamper detection and separate evidence: no sealing certificate, no hashes, no record of IP address or user agent. A signed PDF is protected the way an uploaded scan is, by private storage and the audit log.
- Placing the signature inside the document. Signature lines printed in a contract template or on the mandate stay empty; the signature page follows them.
- Removing the upload.
- Countersigning the registration document or mandates.
- Several signatories having to sign together.

## Capabilities

### New Capabilities
- `document-signing`: signing input, the signature page, online signing of agreement contracts, SEPA mandates and the registration document, and the countersignature on approval.

### Modified Capabilities

None. `organization-agreements` and `sepa-mandates` require a signed document without saying how it is provided; a document signed online is one. For kinds that require a countersignature this change adds a condition to approval and leaves the existing ones in place.

## Impact

- `utils`: a module `signing` with the two form fields and the function that appends the signature page; one template partial; `signature_pad` vendored as a static file; tests.
- `agreements`: `AgreementKind.requires_countersignature`; the signature fields in the application, signed document, mandate and approval forms; `create_agreement`, `upload_signed_document`, `create_mandate`, `upload_signed_mandate` and `approve_agreement` accept a signature.
- `providers`: `Manager.signatory_title`.
- `organizations`, after `organization-terms`: the creation form and `create_organization`.
- No new Python dependencies (`pypdf`, `reportlab` and `Pillow` are in use), no new settings, no new models, no new personal data.
- Legal checks before rollout, listed in the ADR: statutes on membership form, commercial lease text form, the bank's creditor agreement on mandate form.
