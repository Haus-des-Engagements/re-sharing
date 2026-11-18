# 29. Electronic signatures

Date: 2026-11-17

## Status

Accepted

## Context

Contracts, SEPA mandates and the registration document reach the platform as uploads: users print a PDF, sign it, scan it and upload it, or paste a picture of their signature onto it. The signature is wanted as a moral hurdle, not as an effort hurdle. The platform already produces the documents to sign: the contract prefilled from the kind's template and the generated mandate.

A scan is a copy, so it is a simple electronic signature in the sense of eIDAS and does not meet written form. None of the documents requires written form: the registration document is a hurdle we set ourselves, membership is formless unless the statutes say otherwise, coworking needs no form, commercial leases need text form, and a SEPA mandate has to be presentable, not signed in ink.

A first design kept signature records with hashes, IP address and user agent in an app of its own and sealed every PDF with a certificate. That is evidence a scan never offered either, and it would have been most of the work: a certificate to manage, new models and relations, a change to the privacy policy and the most difficult PDF code in the project.

## Decision

Users can sign online wherever a signed PDF is uploaded. The upload stays.

- **Simple electronic signature.** The signer is logged in, types their name and draws their signature. There is no identity check, no third-party service and no qualified signature.
- **The document is the evidence.** The server appends one signature page to the PDF with the drawn signature, the typed name, the function, the party signed for, date and time and the email address of the account. The result is stored in the file field an upload would fill, in private storage. The audit log shows who changed the field and when. Nothing else is recorded: no hashes, no IP address, no seal.
- **One module, no models.** `re_sharing/utils/signing.py` holds the form fields and `append_signature_page`. Callers pass the PDF as bytes and store the result. Whether a stored PDF was signed online or uploaded is not recorded; the file shows it.
- **Every signature appends its own page.** There are no slots and no notion of a complete document. Signature lines printed in a template or on the mandate stay empty.
- **Approving is countersigning.** An agreement kind can require a countersignature. Approving it is then reserved to managers with a signatory title, who sign in the approval form. Their signature page is appended to the stored contract, whether it was signed online or uploaded. There is no separate countersign step and no state between countersigned and active.

## Consequences

- Signing takes a minute on a phone or desktop and needs no printer.
- A signed PDF can be changed by whoever can write to the storage or the database without this being detectable. This is the same as for uploaded scans.
- Beyond the document and the audit log nothing proves that a given person signed. We accept this for documents of this weight.
- Form fields of a signed contract stay editable in a downloaded copy. The stored copy and the agreement's data in the database are what count.
- A manager without signatory title cannot approve kinds that require a countersignature, only reject them.
- A qualified signature would be needed where the law demands written form. It would mean a paid provider and identity checks and is a new decision.

Legal checks before contracts and mandates are opened for online signing:

- the statutes on the form of membership applications,
- that office and cellar leases to associations count as commercial leases under text form,
- the bank's creditor agreement on the form of SEPA mandates.
