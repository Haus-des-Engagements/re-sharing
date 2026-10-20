## Context

After `organization-terms`, registration collects one signed document in `Organization.registration_document` (FileField, private storage, PDF validated) and `registration_document_date`. `organization-agreements` adds two more uploads of the same kind: `Agreement.signed_document` with `signed_on`, and `SepaMandate.signed_document` with `signed_on`. Users fill all of them by printing, signing, scanning and uploading, or by pasting a signature image onto the PDF. In `organization-agreements`, a manager records the board's decision with a date, and approval requires a signed document and an active mandate.

The stakeholder wants the signature as a moral hurdle, not an effort hurdle: typing your name and drawing a signature feels harder to lie on than a checkbox. No third-party signing service unless it is cheap and adds a lot of value. There is a single legal entity. Coworking, office lease and cellar lease contracts are countersigned by one manager who is managing director and signs alone; membership is not countersigned, its decision is recorded by a manager.

Constraints: HackSoft style with services and selectors, coverage above 95 percent, explicit relations between apps (ADR 9), private storage for signed documents (ADR 20), auditlog for model changes (ADR 13), mails enqueued as tasks with attachments supported (`email.attach` is already used for iCal files), IBAN never in emails (`organization-agreements`).

## Goals / Non-Goals

**Goals:**

- Sign a fixed or generated PDF inside re-sharing in under a minute, on desktop and phone.
- Leave stronger evidence than a scan: who, when, from where, and on exactly which bytes.
- Make later modification of a signed PDF detectable.
- One service for registration, contracts and mandates, with countersignatures on the same file.

**Non-Goals:**

- See the proposal. Additionally: verification of a signer's identity beyond their login, and a public verification page.

## Decisions

### D1: Simple electronic signature with an audit trail

The signature is an eIDAS simple electronic signature (SES): login, typed name, drawn image, explicit confirmation, recorded metadata. A scanned handwritten signature, the status quo, is also an SES, because it is a copy and does not meet the written form of §126 BGB. None of the documents requires written form. The registration document is a self-imposed hurdle. Membership is formless unless the statutes say otherwise, and self-imposed written form is met by electronic transmission (§127 BGB). Coworking needs no form. Commercial leases need text form only since 2025. SEPA mandates do not need ink: without proof of a mandate the debtor can claim a refund for 13 months instead of 8 weeks, and the signature record is that proof. A qualified signature (QES) would only be needed where the law demands written form; it would mean a paid provider and identity checks, and is out of scope. Recorded in ADR `0027-Electronic-Signatures.md` together with the legal checks below.

Alternatives: a third-party service such as DocuSign or Skribble (fees, an extra account per signer, more friction than value for an SES); a self-hosted open-source signing tool such as DocuSeal or Documenso (another service to run, and its strengths, such as inviting external signers and placing fields, are not needed when the signer is logged in and the document is ours).

### D2: A leaf app that returns bytes

The `signing` app references only `User`. Its services take the current PDF as bytes and return the signed PDF as bytes together with the records. The caller stores the bytes in its own FileField. The existing fields and their upload fallback stay unchanged, and the signing app knows nothing about organizations, agreements or mandates.

Callers link to the record with a nullable `OneToOneField` to `SignedDocument`, `PROTECT`: `Organization.registration_signed_document`, `Agreement.signed_document_record`, `SepaMandate.signed_document_record`. A null link means the document was uploaded.

Alternative: a generic foreign key from `SignedDocument` to its owner. Rejected, harder to query and to protect, and against ADR 9's preference for explicit relations.

### D3: Three models

`SigningTemplate`: `name`, `slug` (unique), `file` (PDF, private storage), `is_active`. Managed in the admin. Used for the registration document and contract templates.

`SignedDocument`: `template` (nullable FK, `PROTECT`; null for generated mandates), `document_name`, `organization_name`, `key_facts` (JSONField, list of label and value pairs as printed), `source_sha256`, `expected_signatures` (default 1), `contains_bank_data` (bool), `completed_at`, `created_at`. Complete when the number of signatures reaches `expected_signatures`.

`Signature`: `signed_document`, `role` (signer, countersigner), `slot` (1-based position on the signature page), `user`, `typed_name`, `function`, `on_behalf_of`, `confirmation_text`, `signed_at`, `ip_address`, `user_agent`, `sha256_before`, `sha256_after`. Unique on (`signed_document`, `slot`). Read-only in the admin, no delete permission, registered with auditlog.

The PDF itself is not stored in `signing`; the latest after-hash ties the record to the file in the caller's field.

### D4: PDF pipeline

1. Compute the SHA-256 of the source.
2. Render a signature page with reportlab: document name, organization, key facts, source hash, and `expected_signatures` slots. Each slot is a box with a role label ("for <organization>", "for <operator>"), image, name, function and time.
3. For the first signature, draw image, typed name, function and time (Europe/Berlin) into slot 1. Append the page to the source with pypdf. Source pages are copied unchanged.
4. Seal with pyHanko. The first seal is a certification signature with DocMDP permission "fill forms and sign". Empty signature fields are placed over the remaining slots, named `slot-2`, `slot-3`.
5. A later signature signs the empty field `slot-n` in an incremental update. Its visible appearance (image, name, title, time) is the field's appearance stream. The first seal stays valid, and validators show the update as a permitted signature.

One PAdES signature per human signature, each made with the operator's certificate. The certificate says the document came from re-sharing unchanged; the human signer is identified by the visible page and the signature record.

Alternative: draw countersignatures onto the page and re-seal. Rejected, this invalidates the first seal and breaks "the same file".

### D5: Sealing certificate

A PKCS#12 file path and passphrase come from settings (`SIGNING_SEAL_P12_PATH`, `SIGNING_SEAL_P12_PASSPHRASE`). The operator starts with a self-signed certificate for the legal entity. PDF readers then show "signer identity unknown" but still detect modification. A certificate from a trusted list can replace it later without code changes. When no certificate is configured, the PDF is stored unsealed and a warning is logged, so development and most tests need no key. Later signatures on an unsealed document are added unsealed too. Tests for sealing generate a throwaway certificate with `cryptography` in a fixture.

No timestamp authority in this change; the signing time is the server time, also stored in the record.

The operator's name in the countersignature slot comes from `SEPA_CREDITOR_NAME`, because there is one legal entity.

### D6: Drawing and validation

`signature_pad` is vendored as a static file and writes a PNG data URL into a hidden input. A small inline script handles clear and resize. The form field decodes the data URL, refuses anything that is not a PNG or exceeds 200 KB, and refuses a blank drawing (no non-transparent pixel, checked with Pillow). Typed name and function are required, at most 100 characters. The confirmation is a required checkbox. Its text is stored verbatim in the record, with the organization name filled in: "I have read the document and am authorized to sign it on behalf of <organization>." The countersignature form has no function field; the manager's signatory title is used.

The fields form a reusable form mixin. Every form with a sign-online option uses it together with an "upload or sign" choice whose `clean()` requires exactly one of the two. A drawing is never re-rendered after a failed submit. The user draws again, so a signature is always made on the final data.

### D7: Service API

```
sign_document(*, source_pdf, document_name, organization_name, key_facts, signer,
              signing_data, client_meta, expected_signatures=1, template=None,
              contains_bank_data=False) -> (SignedDocument, bytes)

add_signature(*, signed_document, current_pdf, signer, signing_data, client_meta,
              role) -> bytes
```

`add_signature` refuses a complete document, and refuses a `current_pdf` whose hash differs from the latest after-hash, which catches a replaced upload. Views pass IP address (`REMOTE_ADDR`, or the first `X-Forwarded-For` hop behind a trusted proxy) and user agent. The services do not read the request. Callers run them inside their own `transaction.atomic`, and mails are enqueued `on_commit`.

### D8: Signed copies

`signed_document_copy_email(signature_id, file_name)` is enqueued after every signature. The task loads the file from the caller's field through a small resolver passed as dotted path and object id, attaches it as `<document name>.pdf` and sends it to the signer. When a signature completes a document, earlier signers receive the complete PDF too. For `contains_bank_data` documents the email has no attachment and links to the page with the download. Mails are translated like the others.

### D9: Registration

The creation form gets the "sign online or upload" choice when an active template with slug `settings.SIGNING_REGISTRATION_TEMPLATE_SLUG` (default `registration`) exists; otherwise the form is unchanged. `create_organization` saves the organization, calls `sign_document` with the template bytes, the organization's name and address as key facts, and one expected signature, saves the bytes into `registration_document` (`_registration_document_signed.pdf`), sets the date to today and links the record. A failure while signing rolls back the organization. The organization page and the manager list show "signed online by <name>, <time>" when a record is linked.

### D10: Agreement contracts

`AgreementKind` gets `contract_template` (nullable FK to `SigningTemplate`, `PROTECT`) and `requires_countersignature` (bool). Initial configuration: membership with template, no countersignature; coworking, office lease and cellar lease with template and countersignature.

The application form and the signed document upload of `organization-agreements` get the sign-online choice when the kind has an active contract template. Signing uses the template as source and these key facts: kind, amount and interval, start date, end date when set, deposit when required, contact person function, and the kind-specific details with their form labels. `expected_signatures` is 2 for countersigned kinds. The signed bytes go to `Agreement.signed_document`, today to `signed_on`, the record to `signed_document_record`.

Changing the amount or details after signing is not possible for the applicant. Managers who change them in the admin see a warning that the signed contract no longer matches; the key facts in the record stay as signed.

### D11: Countersignature and approval

`Manager` gets `may_countersign` (bool) and `signatory_title` (CharField, required when the flag is set, checked in `clean()`).

A new service `countersign_agreement(manager, agreement, signing_data, client_meta)` in `agreements`:

1. requires `manager.may_countersign`, `manager_can_manage_agreement`, status submitted, a kind with `requires_countersignature`, a linked record with one signature, and an active mandate;
2. calls `add_signature` with role countersigner, the manager's name and title, on behalf of the operator;
3. saves the bytes into `signed_document`;
4. calls `approve_agreement(manager, agreement, decided_at=today)`, so groups, codes, deposit and decision email behave exactly as on approval.

All four steps run in one transaction; if approval fails, nothing is signed.

`approve_agreement` gains one rule: for a kind with `requires_countersignature`, a linked record that is not complete refuses plain approval with a pointer to countersigning. An uploaded contract (no record) is approved as before, because the manager uploads the version signed by both. Rejection is unchanged and open to every manager within scope. The manager agreement list gets a filter "awaiting countersignature".

Alternative: countersign first, approve as a separate click. Rejected, a countersigned contract that is not active is a state nobody wants.

### D12: SEPA mandates

There is no template: the mandate is rendered by reportlab from the standard SEPA core mandate text (German, with an English translation below), followed by creditor name, creditor identifier, mandate reference, account holder, IBAN, BIC, bank name, and type "recurring payment". This page is the source PDF; the signature page follows it with one slot, so mandates look like every other signed document.

`create_mandate` generates the reference first, then signs inside the same transaction, saves the bytes into `SepaMandate.signed_document`, today into `signed_on`, and links the record with `contains_bank_data=True`. The IBAN is printed in full on the PDF, which stays in private storage. Revocation does not touch the PDF.

## Risks / Trade-offs

- [Self-signed seal looks "unknown" in Acrobat] → Integrity is still verifiable. Buying a certificate is a configuration change. Explained in the ADR.
- [Drawing on a phone is fiddly] → The pad scales to the container width, clear is one tap, and upload stays available.
- [IP address and user agent are personal data] → Stored only with signatures, for evidence, with the same retention as the document. One sentence in the privacy policy.
- [Signer is not the legal representative] → The confirmation states the authority, and the function is recorded. Same as on paper.
- [Template replaced while a user has the form open] → The template is loaded at submit time and its hash is recorded.
- [Contract data changed in the admin after signing] → The record keeps the signed key facts; the admin shows a mismatch warning.
- [Uploaded file replaced after an online signature] → `add_signature` checks the hash and refuses; a replaced upload means the record link must be cleared, which the upload service does.
- [pyHanko adds a cryptography stack] → Mature library, pure Python on top of `cryptography`.

## Migration Plan

1. Registration part (tasks 1 to 6) ships after `organization-terms`. Contract, countersignature and mandate parts (tasks 7 to 9) ship after `organization-agreements`, or are folded into its forms if it is still in progress.
2. Deploy the migrations (`signing` models, links on `Organization`, `Agreement`, `SepaMandate`, the kind and manager fields).
3. Create the seal certificate, store it outside the repository, set the two settings.
4. Upload the values sheet as `SigningTemplate` with slug `registration`, and one contract template per kind; set `requires_countersignature` on coworking, office lease and cellar lease.
5. Flag the managing director as `may_countersign` with title.
6. Add the sentence on signature metadata to the privacy policy.
7. Rollback: deactivate templates; forms show only the upload again; a missing countersignature can always be replaced by uploading a contract signed by both. Signed documents stay valid.

Legal checks before opening contracts and mandates online: the statutes on the form of membership applications; that office and cellar leases to associations count as commercial leases under text form; the bank's creditor agreement on the form of SEPA mandates.

## Open Questions

- Whether to add a trusted timestamp (RFC 3161) to seals.
- Whether to buy a certificate from a trusted list for the seal, or stay self-signed.
