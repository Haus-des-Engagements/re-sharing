## Why

Signed documents reach re-sharing as uploads: users download a PDF, print it, sign, scan and upload it, or paste a picture of their signature onto it. A scan is a copy, so legally it is a simple electronic signature already, only without any record of who signed what and when. Signing inside re-sharing keeps the moral weight of a signature, removes the printer, and leaves better evidence than a scan. No third-party service is needed, because none of the documents requires a qualified signature. With `organization-agreements`, contracts and SEPA mandates add two more signed uploads; they should be signed the same way from the start.

## What Changes

- A new `signing` app with a generic signing flow: the user reads the document, types their name, draws their signature and confirms that they sign on behalf of their organization. The function is taken from the form that already asks for it.
- The server appends a signature page to the source PDF: the key facts of the document, one slot per expected signer with signature image, typed name, function and time, and the SHA-256 of the source. When the last expected signature is made, the result is sealed with the operator's own certificate so later changes are detectable. Each signature is stored with user, time, IP address, user agent and the hashes before and after signing.
- A document can expect more than one signature. Later signatures fill the next slot on the same page; the file is sealed once, when complete.
- Signed documents are never emailed, whatever their type. They stay in private storage and are downloaded from the page they belong to. No extra notification: the existing emails of each flow (manager notification at registration, application received, decision) already point to those pages.
- Source PDFs are terms documents (`organization-terms`): the signed registration document's current version, and per agreement kind a contract document. No separate template model; versions and the record of which version was signed come from the terms app.
- **Registration document:** the creation form offers "sign online" next to the upload and fills the same fields.
- **Agreement contracts:** an agreement kind can point at a contract document. The applicant signs its current version online when applying or afterwards; the signature page lists kind, amount, interval, start date, deposit and the kind-specific details.
- **Countersignature:** an agreement kind can require a countersignature (coworking, office lease, cellar lease; not membership). A manager flagged as authorized signatory, with a title such as managing director, countersigns the same file alone. Countersigning is the decision: it completes the contract and approves the agreement with the signing date as decision date.
- **SEPA mandates:** the mandate is generated from the standard mandate text, creditor data, generated reference and bank details, and signed online by the account holder's representative.
- Upload stays as fallback everywhere, for existing paper documents and for users who prefer it.
- ADR on the signature level: simple electronic signature with an audit trail, why it meets or exceeds the status quo, and when a qualified signature would be needed.

### Non-goals

- Advanced or qualified electronic signatures, identity verification, third-party signing services.
- Removing the upload.
- Generating the contract text from data. Contracts are fixed documents per kind; the agreement's data appears on the signature page.
- Countersigning the registration document or mandates.
- Several authorized signatories having to sign together. One authorized manager signs alone.
- Sealing before a document is complete. An incomplete document is protected by its recorded hash and private storage.

## Capabilities

### New Capabilities
- `document-signing`: the signing flow, signature page and seal, signature records, multiple signatures per document, signed copies, and online signing of the registration document, agreement contracts with optional countersignature, and SEPA mandates.

### Modified Capabilities

None. The registration form requirements live in the unarchived change `organization-terms`, the agreement and mandate requirements in `organization-agreements`. Both are worded so that this change adds an alternative way to provide the same signed document: `organization-terms` requires a signed registration document without saying how it is provided, and `organization-agreements` requires a complete signed document, where an upload is always complete and this change defines when an online signature is. This change depends on both; the registration part can ship after `organization-terms` alone.

## Impact

- New app `signing`: models, services, admin, form mixin, a JS signature pad, tests. Leaf app: references only `User`.
- `terms`: no model change; a kind's contract document is a terms document without scopes, and the signed registration document is the one with the signature flag.
- `organizations`: nullable relation `registration_document_record` from `Organization` to the signature record, creation form and template, `create_organization`, show page and manager list.
- `agreements`: `AgreementKind.contract_document` and `requires_countersignature`; `signed_document_record` on `Agreement` and `SepaMandate`; sign-online options in the application, upload and mandate forms; a countersign-and-approve action; the decision email names the contract on the agreement page.
- `providers`: `Manager.may_countersign` and `signatory_title`.
- New dependencies: `pyhanko` (sealing), `pypdf` (appending and overlaying pages), `reportlab` (rendering pages), `signature_pad` (vendored JS).
- New settings: path to the sealing certificate and key, key passphrase. Sealing is skipped with a warning when no certificate is configured (development, tests by default).
- Personal data: IP address and user agent are stored with each signature; the privacy policy needs a sentence about it. Signed documents, including mandates with the IBAN, stay in private storage and never leave the system by email.
- Legal checks before rollout, listed in the ADR: statutes on membership form, commercial lease text form, the bank's creditor agreement on mandate form.
