## Context

Three file fields hold signed PDFs, each with a signing date: `Agreement.signed_document`, `SepaMandate.signed_document` and the organization's registration document (`usage_agreement` today, `registration_document` after `organization-terms`). Users fill them by printing, signing, scanning and uploading.

`agreement-documents` already produces what is signed. `prefilled_contract(agreement, person)` fills the kind's `contract_template` with the agreement's data, also for an agreement that is not saved yet. `render_mandate(mandate)` renders the mandate with creditor data, reference and bank details. Both are offered for download before and after saving. Approval requires a signed contract and an active mandate, which is a mandate with a signed PDF that is not revoked.

The stakeholder wants the signature as a moral hurdle, not an effort hurdle: typing your name and drawing a signature feels harder to lie on than a checkbox. No third-party signing service. There is one legal entity. Coworking and lease contracts are countersigned by one manager who is managing director and signs alone; membership is not countersigned.

An earlier version of this change added a signing app with signature records, a hash chain, IP addresses and a sealed PDF. That protects against disputes nobody has had with scans and costs more than the rest of the feature. This version keeps only what the user sees.

## Goals / Non-Goals

**Goals:**

- Sign a document inside re-sharing in under a minute, on desktop and phone.
- A signed PDF that shows who signed, in which function, for whom and when.
- As little new code and state as possible: no models, no settings, no new Python dependencies.

**Non-Goals:**

- See the proposal. Evidence beyond the document, and detecting later changes to it, are explicitly left out.

## Decisions

### D1: Simple electronic signature, the document is the evidence

The signature is an eIDAS simple electronic signature: login, typed name, drawn image. A scanned handwritten signature, the status quo, is the same level, because a scan is a copy. None of the documents requires written form. The registration document is a self-imposed hurdle. Membership is formless unless the statutes say otherwise. Coworking needs no form. Commercial leases need text form only. SEPA mandates need no ink; what matters is that a mandate can be shown.

What is kept as evidence is the PDF with its signature page, in private storage, plus the audit log entry that the file field changed, with user and time. That is more than a scan offers and enough for documents of this weight. A qualified signature would only be needed where the law demands written form and is out of scope. Recorded in an ADR `Electronic-Signatures` with the legal checks below.

Alternatives: a third-party or self-hosted signing service (cost and another system for no value at this level); signature records with hashes, IP address and a sealed PDF (the earlier design; a certificate to manage, two models, three relations, a privacy policy change and the hardest PDF code in the project, to prove something a scan never proved either).

### D2: One module, no models

A module `re_sharing/utils/signing.py` holds two things: the form fields (D4) and

```
append_signature_page(pdf, *, document_name, on_behalf_of, name, function,
                      image, user, signed_at) -> bytes
```

Callers pass the PDF to sign as bytes and save the result in their existing file field with today's date as signing date. Whether a stored PDF was signed online or uploaded is not recorded; the file shows it. The module knows nothing about organizations, agreements or mandates.

### D3: Signature page

`append_signature_page` renders one A4 page with reportlab and appends it with pypdf. The source pages are copied unchanged. The page shows a heading, the document name, the party signed for, the drawn signature, the typed name, the function, date and time in Europe/Berlin, the email address of the account that signed, and the sentence the signer saw (D4).

Every signature appends its own page. A countersigned contract therefore ends with two signature pages. There are no slots, no overlay onto an existing page and no notion of a document being complete.

Signature lines printed in a contract template or on the mandate stay empty. Form fields of the prefilled contract stay editable in the signed copy, as in the download; the stored file and the agreement's data in the database are what count.

### D4: Input

`signature_pad` is vendored into `static/js/vendors/` and writes a PNG data URL into a hidden input. One template partial renders the name field, the pad, a clear button and the sentence "By signing I confirm that I have read the document and may sign it on behalf of <party>." There is no checkbox; drawing is the confirmation.

Two form fields in a mixin: `signature_name` (at most 100 characters) and `signature_image`. The image field decodes the data URL and refuses anything Pillow does not open as a PNG or that exceeds 200 KB. An empty pad is caught in the browser; the server does not inspect pixels. `clean()` requires name and drawing together, and refuses a drawing together with an upload. A drawing is not rendered again after a failed submit; the user draws again.

The function is never typed for signing: contracts and mandates use the agreement's `contact_person_function`, the countersignature the manager's signatory title, and the registration form asks for it as part of the form.

### D5: Agreement contracts

The application form and the signed document form show the signature fields when the kind has a contract template. With a signature, `create_agreement` and `upload_signed_document` call `prefilled_contract(agreement, user)`, append the signature page for the organization and store the result in `signed_document` with `signed_on` set to today. `has_complete_signed_document` stays as it is: a stored file is complete.

Signing afterwards is offered while the agreement is submitted. An active agreement keeps only the upload, so signing again cannot drop a countersignature page. Kinds without a template offer only the upload. The manager forms for entering paper applications do not offer signing, because the manager is not the organization's signer.

### D6: SEPA mandates

The mandate form and the signed mandate form show the signature fields. With a signature, `create_mandate` and `upload_signed_mandate` call `render_mandate(mandate)`, append the signature page for the organization and store the result in `signed_document` with `signed_on`. The mandate is then active by the existing rule. The reference is generated before rendering, as it is today for the download.

### D7: Countersignature on approval

`AgreementKind` gets `requires_countersignature` (bool). `Manager` gets `signatory_title` (CharField, blank); a manager with a title is an authorized signatory.

For a kind with the flag, the approval form on the agreement page shows the signature fields, and `approve_agreement` additionally requires that the approving manager has a signatory title and signs. It appends a signature page on behalf of the operator (`SEPA_CREDITOR_NAME`) with the manager's typed name and title to the stored contract, then approves as today, in the same transaction. The decision date is the one entered in the form.

This works on whatever is stored, a contract signed online or an uploaded scan, so there is one path. A contract already signed by both on paper gets the page as well. Rejection is unchanged and open to every manager in scope. Kinds without the flag are approved as today.

Alternatives: a separate countersign action before approval (a second state "countersigned but not active" nobody wants, plus a filter and messages pointing from one action to the other); a second slot on the applicant's signature page (requires knowing that the stored file is ours and where to draw); a flag next to the title (a title without the flag means nothing).

### D8: Registration document

After `organization-terms` the registration document is a terms document whose current version holds a PDF. When that version has a file, the creation form shows the signature fields and a function field next to the upload. With a signature, `create_organization` appends the signature page to that file on behalf of the organization, named with its address, and stores the result in `registration_document` with today's date. Everything else, including the terms acceptance, is as for an upload. Without such a file the form is unchanged.

### D9: The upload stays

Every form that offers signing keeps its upload and the existing download of the document. A later upload replaces the file as it does today, also one signed online. Nothing needs to be cleared, because nothing but the file is stored.

## Risks / Trade-offs

- [A signed PDF can be changed by whoever can write to storage or the database, undetected] → Same as for uploaded scans. The audit log shows changes made through the application.
- [No proof beyond the document that a given person signed] → The page names the account; the audit log names the user who set the file. Accepted for these documents.
- [Signer is not the legal representative] → The sentence on the page states the authority and the function is printed. Same as on paper.
- [The signature is on an extra page, signature lines in the document stay empty] → The page names the document and the party. Templates can drop their signature lines over time.
- [Form fields of a signed contract stay editable in a downloaded copy] → The stored copy counts, and the agreement's data is in the database.
- [A manager without signatory title cannot approve countersigned kinds] → Intended; they can still reject. The managing director approves in one step.
- [A blank or scribbled drawing passes the server] → A manager sees the contract before approving; a mandate is the organization's own risk.
- [Drawing on a phone is fiddly] → The pad scales to the container width, clear is one tap, upload stays available.

## Migration Plan

1. Contracts, mandates and the countersignature build on what is deployed. The registration part ships after `organization-terms`.
2. Deploy the migration with the two fields.
3. Set `requires_countersignature` on coworking, office lease and cellar lease, and the signatory title of the managing director.
4. Rollback: revert the release. Documents signed until then are ordinary PDFs in the existing fields and stay valid.

Legal checks before opening contracts and mandates online: the statutes on the form of membership applications; that office and cellar leases to associations count as commercial leases under text form; the bank's creditor agreement on the form of SEPA mandates.
