## Context

After `organization-terms`, registration collects one signed document in `Organization.registration_document` (FileField, private storage, PDF validated) and `registration_document_date`, and the document itself is a terms document with the signature flag whose current version holds the PDF. `organization-agreements` adds two more uploads of the same kind: `Agreement.signed_document` with `signed_on`, and `SepaMandate.signed_document` with `signed_on`. Users fill all of them by printing, signing, scanning and uploading, or by pasting a signature image onto the PDF. In `organization-agreements`, approval requires a complete signed document, where an upload is complete, and an active mandate, which is a mandate with a signed PDF that is not revoked. A mandate can be saved with bank data before its signed PDF exists. Applicants download the contract from a link in the kind's intro text and the mandate as a blank form. That change knows only a decision recorded by a manager; countersigning as the decision is added here.

The stakeholder wants the signature as a moral hurdle, not an effort hurdle: typing your name and drawing a signature feels harder to lie on than a checkbox. No third-party signing service unless it is cheap and adds a lot of value. There is a single legal entity. Coworking, office lease and cellar lease contracts are countersigned by one manager who is managing director and signs alone; membership is not countersigned, its decision is recorded by a manager.

Constraints: HackSoft style with services and selectors, coverage above 95 percent, minimal relations between apps (ADR 9), private storage for signed documents (ADR 20), auditlog for model changes (ADR 13), mails enqueued as tasks, IBAN never in emails (`organization-agreements`).

## Goals / Non-Goals

**Goals:**

- Sign a fixed or generated PDF inside re-sharing in under a minute, on desktop and phone.
- Leave stronger evidence than a scan: who, when, from where, and on exactly which bytes.
- Make later modification of a completed signed PDF detectable.
- One service for registration, contracts and mandates, with countersignatures on the same file.

**Non-Goals:**

- See the proposal. Additionally: verification of a signer's identity beyond their login, and a public verification page.

## Decisions

### D1: Simple electronic signature with an audit trail

The signature is an eIDAS simple electronic signature (SES): login, typed name, drawn image, explicit confirmation, recorded metadata. A scanned handwritten signature, the status quo, is also an SES, because it is a copy and does not meet the written form of §126 BGB. None of the documents requires written form. The registration document is a self-imposed hurdle. Membership is formless unless the statutes say otherwise, and self-imposed written form is met by electronic transmission (§127 BGB). Coworking needs no form. Commercial leases need text form only since 2025. SEPA mandates do not need ink: without proof of a mandate the debtor can claim a refund for 13 months instead of 8 weeks, and the signature record is that proof. A qualified signature (QES) would only be needed where the law demands written form; it would mean a paid provider and identity checks, and is out of scope. Recorded in an ADR `Electronic-Signatures` together with the legal checks below.

Alternatives: a third-party service such as DocuSign or Skribble (fees, an extra account per signer, more friction than value for an SES); a self-hosted open-source signing tool such as DocuSeal or Documenso (another service to run, and its strengths, such as inviting external signers and placing fields, are not needed when the signer is logged in and the document is ours).

### D2: A leaf app that returns bytes

The `signing` app references only `User`. Its services take the current PDF as bytes and return the signed PDF as bytes together with the records. The caller stores the bytes in its own FileField. The existing fields and their upload fallback stay unchanged, and the signing app knows nothing about organizations, agreements, mandates or terms.

Callers link to the record with a nullable `OneToOneField` to `SignedDocument`, `PROTECT`, named after the file field: `Organization.registration_document_record`, `Agreement.signed_document_record`, `SepaMandate.signed_document_record`. A null link means the document was uploaded.

Source PDFs come from the terms app: the current version of the registration document with the signature flag, and the current version of a kind's contract document. Which version was signed is recorded by the caller, as a terms acceptance at registration and as the version label in the document name on the signature page for contracts. The signing app itself keeps only the source hash.

Alternatives: a generic foreign key from `SignedDocument` to its owner (harder to query and to protect, and against ADR 9's preference for explicit relations); a template model in `signing` (a second registry of managed PDFs next to terms versions, with no version history).

### D3: Two models

`SignedDocument`: `document_name`, `organization_name`, `key_facts` (JSONField, list of label and value pairs as printed), `source_sha256`, `expected_signatures` (default 1), `completed_at`, `created_at`. Complete when the number of signatures reaches `expected_signatures`.

`Signature`: `signed_document`, `role` (signer, countersigner), `user`, `typed_name`, `function`, `on_behalf_of`, `confirmation_text`, `signed_at`, `ip_address`, `user_agent`, `sha256_before`, `sha256_after`. Unique on (`signed_document`, `role`); the role fixes the slot on the page (signer first, countersigner second). Read-only in the admin, no delete permission, registered with auditlog.

The PDF itself is not stored in `signing`; the latest after-hash ties the record to the file in the caller's field.

### D4: PDF pipeline

1. Compute the SHA-256 of the source.
2. First signature: render a signature page with reportlab: document name, organization, key facts, source hash, and one slot per expected signature. Each slot is a box with a role label ("for <organization>", "for <operator>"). Draw image, typed name, function and time (Europe/Berlin) into the first slot. Append the page to the source with pypdf. Source pages are copied unchanged.
3. Later signature: verify that the hash of the stored PDF equals the latest after-hash, render an overlay with the signature for the next slot, and merge it onto the signature page with pypdf. Source pages stay unchanged.
4. When the number of signatures reaches `expected_signatures`, seal with pyHanko: one PAdES signature with the operator's certificate covering the whole document. Before that the file is stored unsealed; the recorded hashes and private storage protect it meanwhile.

The seal says the document left re-sharing complete and unchanged; the human signers are identified by the visible page and the signature records.

Alternative: seal after every signature and add later signatures as incremental updates with pre-placed signature fields and DocMDP permissions, so that earlier seals stay valid. Rejected, every seal would be the operator's certificate anyway, the hash chain in the records already proves the order, and the incremental-update machinery is the hardest part of the stack for no gain in evidence.

### D5: Sealing certificate

A PKCS#12 file path and passphrase come from settings (`SIGNING_SEAL_P12_PATH`, `SIGNING_SEAL_P12_PASSPHRASE`). The operator starts with a self-signed certificate for the legal entity. PDF readers then show "signer identity unknown" but still detect modification. A certificate from a trusted list can replace it later without code changes. When no certificate is configured, the PDF is stored unsealed and a warning is logged, so development and most tests need no key. Tests for sealing generate a throwaway certificate with `cryptography` in a fixture.

No timestamp authority in this change; the signing time is the server time, also stored in the record.

The operator's name in the countersignature slot comes from `SEPA_CREDITOR_NAME`, because there is one legal entity.

### D6: Drawing and validation

`signature_pad` is vendored as a static file and writes a PNG data URL into a hidden input. A small inline script handles clear and resize. The form field decodes the data URL, refuses anything that is not a PNG or exceeds 200 KB, and refuses a blank drawing (no non-transparent pixel, checked with Pillow). The typed name is required, at most 100 characters. The confirmation is a required checkbox. Its text is stored verbatim in the record, with the organization name filled in: "I have read the document and am authorized to sign it on behalf of <organization>."

The fields form a reusable form mixin: name, drawing, confirmation, and an "upload or sign" choice whose `clean()` requires exactly one of the two. The function is never typed twice: the registration form adds a function field to the mixin, the agreement application and upload forms use the agreement's `contact_person_function`, the mandate form uses the same value from the agreement, and the countersignature uses the manager's signatory title. A drawing is never re-rendered after a failed submit. The user draws again, so a signature is always made on the final data.

### D7: Service API

```
sign_document(*, source_pdf, document_name, organization_name, key_facts, signer,
              signing_data, client_meta, expected_signatures=1) -> (SignedDocument, bytes)

add_signature(*, signed_document, current_pdf, signer, signing_data, client_meta,
              role) -> bytes
```

`add_signature` refuses a complete document, and refuses a `current_pdf` whose hash differs from the latest after-hash, which catches a replaced upload. Views pass IP address (`REMOTE_ADDR`, or the first `X-Forwarded-For` hop behind a trusted proxy) and user agent. The services do not read the request. Callers run them inside their own `transaction.atomic`. The signing date stored by callers is the signature's Europe/Berlin date.

### D8: Documents stay in the system

Signed documents are never attached to emails, whatever their type. This keeps one rule for all documents instead of an exception for mandates with bank data, and keeps signed files out of mailboxes. They stay in private storage and are downloaded from the caller's page through the existing private-storage URLs, which only those pages render: the organization page, the agreement page, the mandate page. Access follows those pages' permissions.

No signing notification is sent. Each flow already has an email that points to the page: the manager notification at registration, the application received email, and the decision email, which for countersigned kinds names the countersigned contract on the agreement page.

Alternatives: attach the PDF and make an exception for mandates (rejected by the stakeholder); a notification after every signature (an applicant signing contract and mandate would receive three emails within a minute, and the existing ones already link to the page).

### D9: Registration

The creation form gets the "sign online or upload" choice when the active registration document with the signature flag has a current version with a file; otherwise the form is unchanged. `create_organization` saves the organization, calls `sign_document` with that version's file, the organization's name and address as key facts, and one expected signature, saves the bytes into `registration_document` (`_registration_document_signed.pdf`), sets the date to the signing date and links the record. The terms acceptance of that version is recorded as for any registration document (`organization-terms` D5). A failure while signing rolls back the organization. The organization page and the manager list show "signed online by <name>, <time>" when a record is linked.

### D10: Agreement contracts

`AgreementKind` gets `contract_document` (nullable FK to `terms.TermsDocument`, `PROTECT`) and `requires_countersignature` (bool). Initial configuration: membership with contract document, no countersignature; coworking, office lease and cellar lease with contract document and countersignature. The contract documents are terms documents without scopes.

The application form and the signed document upload of `organization-agreements` get the sign-online choice when the kind's contract document has a current version with a file. Signing uses that file as source, the document name with the version label, and these key facts: kind, amount and interval, start date, end date when set, deposit when required, contact person function, and the kind-specific details with their form labels. `expected_signatures` is 2 for countersigned kinds. The signed bytes go to `Agreement.signed_document`, the signing date to `signed_on`, the record to `signed_document_record`. An agreement's signed document is complete when it was uploaded or when its record is complete.

Changing the amount or details after signing is not possible for the applicant. Managers who change them in the admin see a warning that the signed contract no longer matches; the key facts in the record stay as signed.

### D11: Countersignature and approval

`Manager` gets `may_countersign` (bool) and `signatory_title` (CharField, required when the flag is set, checked in `clean()`).

A new service `countersign_agreement(manager, agreement, signing_data, client_meta)` in `agreements`:

1. requires `manager.may_countersign`, `manager_can_manage_agreement`, status submitted, a kind with `requires_countersignature`, a linked record with one signature, and an active mandate;
2. calls `add_signature` with role countersigner, the manager's name and title, on behalf of the operator; the document becomes complete and sealed;
3. saves the bytes into `signed_document`;
4. calls `approve_agreement(manager, agreement, decided_at=<signing date>)`, so groups, codes, deposit and decision email behave exactly as on approval.

All four steps run in one transaction; if approval fails, nothing is signed.

`approve_agreement` already requires a complete signed document (`organization-agreements`). For a kind with `requires_countersignature` and a linked record that is not complete, its refusal message points to countersigning. An uploaded contract (no record) is approved as before, because the manager uploads the version signed by both. Rejection is unchanged and open to every manager within scope. The manager agreement list gets a filter "awaiting countersignature".

Alternative: countersign first, approve as a separate click. Rejected, a countersigned contract that is not active is a state nobody wants.

### D12: SEPA mandates

There is no source document: the mandate is rendered by reportlab from the standard SEPA core mandate text (German, with an English translation below), followed by creditor name, creditor identifier, mandate reference, account holder, IBAN, BIC, bank name, and type "recurring payment". This page is the source PDF; the signature page follows it with one slot, so mandates look like every other signed document.

`create_mandate` generates the reference first, then signs inside the same transaction, saves the bytes into `SepaMandate.signed_document`, the signing date into `signed_on`, and links the record. A mandate saved without signed PDF can be signed online later from its page with `sign_mandate(user, mandate, signing_data, client_meta)`, which renders from the stored data.

### D13: Signing by hand stays possible

Every form that offers online signing keeps the upload and links the document for download in both paths: the registration form links the current version of the signed registration document (`organization-terms` D1), the application and upload forms link the current version of the kind's contract document instead of the intro text link, and the page of a mandate without signed PDF offers the mandate rendered by D12 without signature page, with reference and bank data filled in, instead of the blank form.

An upload always wins. It replaces the file, stores the typed signing date and clears the record link; the record itself stays as evidence. A contract the applicant signed online and the authorized manager countersigns on paper is therefore downloaded from the agreement page, signed, uploaded by the manager and approved as an uploaded contract. A contract the applicant uploaded has no record and is countersigned the same way, on paper. The sign-online option is offered only where the document can still be signed, so a document with a record that is complete is replaced only by an upload. The IBAN is printed in full on the PDF, which stays in private storage and is downloadable from the mandate page as `organization-agreements` states. Revocation does not touch the PDF.

## Risks / Trade-offs

- [Self-signed seal looks "unknown" in Acrobat] → Integrity is still verifiable. Buying a certificate is a configuration change. Explained in the ADR.
- [Incomplete document is unsealed for days] → Only countersigned contracts wait. The file is in private storage, its hash is recorded, and `add_signature` refuses a changed file.
- [Drawing on a phone is fiddly] → The pad scales to the container width, clear is one tap, and upload stays available.
- [IP address and user agent are personal data] → Stored only with signatures, for evidence, with the same retention as the document. One sentence in the privacy policy.
- [Signer is not the legal representative] → The confirmation states the authority, and the function is recorded. Same as on paper.
- [Terms version replaced while a user has the form open] → The current version is loaded at submit time and its hash is recorded; versions are never edited, so the hash identifies the version.
- [Contract data changed in the admin after signing] → The record keeps the signed key facts; the admin shows a mismatch warning.
- [Uploaded file replaced after an online signature] → `add_signature` checks the hash and refuses; a replaced upload means the record link must be cleared, which the upload service does (D13).
- [pyHanko adds a cryptography stack] → Mature library, pure Python on top of `cryptography`.

## Migration Plan

1. The signing core (tasks 1 to 4) depends on neither change. The registration part (task 5) ships after `organization-terms`, contracts and countersignature (task 6) after `organization-agreements` and `organization-terms`, mandates (task 7) after `organization-agreements`. Planned order: `organization-agreements`, `organization-terms`, this change.
2. Deploy the migrations (`signing` models, links on `Organization`, `Agreement`, `SepaMandate`, the kind and manager fields).
3. Create the seal certificate, store it outside the repository, set the two settings.
4. In the terms admin, make sure the values sheet (registration scope, signature flag) has a current version with a file; create one contract document without scopes per kind with its current version; point each kind at its contract document and set `requires_countersignature` on coworking, office lease and cellar lease.
5. Flag the managing director as `may_countersign` with title.
6. Add the sentence on signature metadata to the privacy policy.
7. Rollback: clear the kinds' contract documents and remove the version file of the registration document; forms show only the upload again; a missing countersignature can always be replaced by uploading a contract signed by both. Signed documents stay valid.

Legal checks before opening contracts and mandates online: the statutes on the form of membership applications; that office and cellar leases to associations count as commercial leases under text form; the bank's creditor agreement on the form of SEPA mandates.

## Open Questions

- Whether to add a trusted timestamp (RFC 3161) to seals.
- Whether to buy a certificate from a trusted list for the seal, or stay self-signed.
