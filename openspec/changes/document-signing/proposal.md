## Why

Signed documents reach re-sharing as uploads: users download a PDF, print it, sign, scan and upload it, or paste a picture of their signature onto it. A scan is a copy, so legally it is a simple electronic signature already, only without any record of who signed what and when. Signing inside re-sharing keeps the moral weight of a signature, removes the printer, and leaves better evidence than a scan. No third-party service is needed, because none of the documents requires a qualified signature. With `organization-agreements`, contracts and SEPA mandates add two more signed uploads; they should be signed the same way from the start.

## What Changes

- A new `signing` app with a generic signing flow: the user reads the document, types their name and function, draws their signature and confirms that they sign on behalf of their organization.
- The server appends a signature page to the source PDF: the key facts of the document, one slot per expected signer with signature image, typed name, function and time, and the SHA-256 of the source. It then seals the result with the operator's own certificate so later changes are detectable. Each signature is stored with user, time, IP address, user agent and the hashes before and after signing.
- A document can expect more than one signature. Later signatures are added in incremental updates to the same file, so the first seal stays valid.
- Signed documents are never emailed, whatever their type. They stay in private storage and can be downloaded from the page they belong to. Signers receive a notification without attachment that links to that page.
- Templates for signable documents are managed in the admin.
- **Registration document:** the creation form offers "sign online" next to the upload and fills the same fields.
- **Agreement contracts:** an agreement kind can have a contract template. The applicant signs it online when applying or afterwards; the signature page lists kind, amount, interval, start date, deposit and the kind-specific details.
- **Countersignature:** an agreement kind can require a countersignature (coworking, office lease, cellar lease; not membership). A manager flagged as authorized signatory, with a title such as managing director, countersigns the same file alone. Countersigning is the decision: it approves the agreement with the signing time as decision date.
- **SEPA mandates:** the mandate is generated from the standard mandate text, creditor data, generated reference and bank details, and signed online by the account holder's representative.
- Upload stays as fallback everywhere, for existing paper documents and for users who prefer it.
- ADR on the signature level: simple electronic signature with an audit trail, why it meets or exceeds the status quo, and when a qualified signature would be needed.

### Non-goals

- Advanced or qualified electronic signatures, identity verification, third-party signing services.
- Removing the upload.
- Generating the contract text from data. Contracts are fixed templates per kind; the agreement's data appears on the signature page.
- Countersigning the registration document or mandates.
- Several authorized signatories having to sign together. One authorized manager signs alone.

## Capabilities

### New Capabilities
- `document-signing`: signable templates, the signing flow, signature page and seal, signature records, multiple signatures per document, signed copies, and online signing of the registration document, agreement contracts with optional countersignature, and SEPA mandates.

### Modified Capabilities

None. The registration form requirements live in the unarchived change `organization-terms`, the agreement and mandate requirements in the unarchived change `organization-agreements`. This change adds an alternative way to fill the same fields and replaces the manager's decision by the countersignature for countersigned kinds. It depends on both changes; the registration part can ship after `organization-terms` alone.

## Impact

- New app `signing`: models, services, selectors, admin, form mixin, a JS signature pad, mails, tests. Leaf app: references only `User`.
- `organizations`: nullable relation from `Organization` to the signature record, creation form and template, `create_organization`, show page and manager list.
- `agreements`: `AgreementKind.contract_template` and `requires_countersignature`; relations from `Agreement` and `SepaMandate` to the signature record; sign-online options in the application, upload and mandate forms; a countersign-and-approve action; approval rules per kind.
- `providers`: `Manager.may_countersign` and `signatory_title`.
- New dependencies: `pyhanko` (sealing), `pypdf` (appending pages), `reportlab` (rendering pages), `signature_pad` (vendored JS).
- New settings: path to the sealing certificate and key, key passphrase, the slug of the registration template. Sealing is skipped with a warning when no certificate is configured (development, tests by default).
- Personal data: IP address and user agent are stored with each signature; the privacy policy needs a sentence about it. Signed documents, including mandates with the IBAN, stay in private storage and never leave the system by email.
- Legal checks before rollout, listed in the ADR: statutes on membership form, commercial lease text form, the bank's creditor agreement on mandate form.
