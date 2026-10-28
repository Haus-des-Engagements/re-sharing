## ADDED Requirements

### Requirement: Signing captures a deliberate act

The signing form SHALL require the typed full name, a drawn signature and a checked confirmation stating that the signer has read the document and is authorized to sign on behalf of the named organization. The signer's function SHALL be recorded from the form that already collects it and SHALL NOT be asked twice. The document SHALL be viewable from the form before signing. An empty or missing drawing SHALL be refused.

#### Scenario: Complete signature accepted

- **WHEN** a logged-in user submits name, a drawn signature and the confirmation
- **THEN** the signature is accepted

#### Scenario: Missing drawing refused

- **WHEN** a user submits the form without drawing a signature
- **THEN** the form is invalid and nothing is signed

#### Scenario: Missing confirmation refused

- **WHEN** a user submits the form without checking the confirmation
- **THEN** the form is invalid and nothing is signed

### Requirement: Signed PDF carries a signature page

Signing SHALL produce a PDF consisting of the unchanged source pages followed by one signature page. The signature page SHALL show the document name, the organization, the key facts passed by the caller as label and value pairs, the SHA-256 of the source PDF, and per signature slot a role label, the drawn signature, typed name, function and date and time in Europe/Berlin. The page SHALL reserve one slot per expected signer.

#### Scenario: Signature page appended

- **WHEN** a user signs a three-page source
- **THEN** the resulting PDF has four pages, the first three identical to the source
- **AND** the fourth page shows the signer's name, function, organization, signing time and the source's SHA-256

#### Scenario: Source version replaced after signing

- **WHEN** the terms version a document was signed from is superseded by a new version
- **THEN** the signature record still holds the hash of the file it was signed on

### Requirement: Complete documents are sealed

When the last expected signature is made and a sealing certificate is configured, the PDF SHALL be sealed with it so that later modification is detectable. Without a certificate the PDF SHALL be stored unsealed and a warning logged. Documents awaiting further signatures SHALL be stored unsealed.

#### Scenario: Sealed when complete

- **WHEN** the only expected signer signs while a sealing certificate is configured
- **THEN** the resulting PDF carries a valid seal covering the whole document

#### Scenario: Unsealed without certificate

- **WHEN** a user signs while no sealing certificate is configured
- **THEN** the resulting PDF is stored without seal
- **AND** a warning is logged

#### Scenario: Awaiting countersignature

- **WHEN** the first of two expected signers signs
- **THEN** the resulting PDF is stored without seal

#### Scenario: Tampering detectable

- **WHEN** a sealed PDF is modified outside re-sharing
- **THEN** seal validation reports the modification

### Requirement: Signature record

Every signature SHALL be recorded with the signed document it belongs to, its role, the signing user, typed name, function, organization name as shown, the confirmation text, time, IP address, user agent, the SHA-256 of the PDF before signing and of the PDF after signing. A signed document SHALL record the SHA-256 of the source, the number of expected signatures and whether it is complete. Signature records SHALL be read-only in the admin.

#### Scenario: Record created on signing

- **WHEN** a user signs a document
- **THEN** one signature record with all listed fields exists for it
- **AND** the after-hash equals the SHA-256 of the stored PDF

#### Scenario: One-signer document complete

- **WHEN** the only expected signer signs
- **THEN** the signed document is complete

#### Scenario: Record not editable

- **WHEN** staff open a signature record in the admin
- **THEN** all fields are read-only and the record cannot be deleted

### Requirement: Signed documents stay in the system

The system SHALL NOT attach signed documents to emails, regardless of their type, and SHALL NOT send a separate notification for a signature. A signed document SHALL be downloadable from the page it belongs to by the users allowed to see that page: the organization page for the registration document, the agreement page for contracts, the mandate page for mandates. The decision email of a countersigned agreement SHALL name the countersigned contract on the agreement page.

#### Scenario: No email on signing

- **WHEN** a user signs a document
- **THEN** no email beyond those of the surrounding flow is enqueued

#### Scenario: Decision email after countersignature

- **WHEN** a countersigner signs a document an applicant signed before
- **THEN** the decision email names the countersigned contract and links the agreement page
- **AND** it has no attachment

#### Scenario: Download restricted to the page's viewers

- **WHEN** a user who may not view an agreement requests its signed document
- **THEN** access is denied

### Requirement: Later signatures fill the next slot

A document expecting more than one signature SHALL accept further signatures in the next free slot of the same signature page. Signing a complete document SHALL be refused. A document SHALL become complete when its signature count reaches the expected number, and SHALL then be sealed as a complete document.

#### Scenario: Second signature added

- **WHEN** a second signer signs a document expecting two signatures
- **THEN** slot 2 shows the second signer's signature, name, function and time
- **AND** the source pages and slot 1 are unchanged
- **AND** the document is complete and sealed

#### Scenario: Signing a complete document

- **WHEN** a user tries to sign a document that is complete
- **THEN** the action is refused and the PDF is unchanged

#### Scenario: Stored PDF does not match record

- **WHEN** a further signature is requested and the stored PDF's SHA-256 differs from the after-hash of the latest signature
- **THEN** the action is refused and the mismatch is logged

### Requirement: Registration document can be signed online

The organization creation form SHALL offer signing the registration document online as an alternative to uploading it, when the registration document with the signature flag has a current version with a file. Exactly one of upload or online signature SHALL be provided. On creation with an online signature, the system SHALL sign that version on behalf of the new organization, store the signed PDF as the organization's registration document, set the registration document date to the signing date, and link the organization to the signed document. The organization page SHALL show who signed online and when; an uploaded document SHALL be shown as uploaded.

#### Scenario: Registration signed online

- **WHEN** a user creates an organization choosing online signing with name, function, drawing and confirmation
- **THEN** the organization's registration document is the signed PDF
- **AND** its registration document date is the signing date
- **AND** the organization is linked to a complete signed document whose signer is the user

#### Scenario: Registration uploaded

- **WHEN** a user creates an organization with an uploaded PDF and signing date
- **THEN** the organization is created as before, with no signed document linked

#### Scenario: Neither upload nor signature

- **WHEN** a user submits the creation form with neither an upload nor an online signature
- **THEN** the form is invalid

#### Scenario: Both upload and signature

- **WHEN** a user submits the creation form with an upload and an online signature
- **THEN** the form is invalid with a message to choose one

#### Scenario: No signable version configured

- **WHEN** no active registration document with the signature flag has a current version with a file
- **THEN** the creation form offers only the upload

#### Scenario: Failed form keeps nothing signed

- **WHEN** the creation form is invalid for another field while a signature was drawn
- **THEN** no signed document is created
- **AND** the user must draw again after correcting the form

#### Scenario: Organization page shows online signature

- **WHEN** a user views an organization whose registration document was signed online
- **THEN** the page shows the signer's name and the signing time

### Requirement: Agreement contract can be signed online

An agreement kind SHALL optionally point at a contract document in the terms app. For kinds whose contract document has a current version with a file, the application form and the signed document upload SHALL offer signing online as an alternative to uploading, with exactly one of the two. Signing SHALL use that version as source, the document name with the version label, the organization as party, and the agreement's kind, amount, billing interval, start date, deposit amount, contact person function and kind-specific details as key facts. The signed PDF SHALL be stored as the agreement's signed document with the signing date, and the agreement SHALL be linked to the signed document. A signed document SHALL expect two signatures when the kind requires a countersignature, otherwise one. An agreement's signed document SHALL count as complete when it was uploaded or when its linked signed document is complete. Kinds without a contract document SHALL offer only the upload.

#### Scenario: Membership contract signed with the application

- **WHEN** a confirmed admin applies for membership and signs online
- **THEN** the agreement has the signed PDF as signed document and the signing date
- **AND** its signed document is complete with one signature
- **AND** the signature page lists kind, amount, interval and start date

#### Scenario: Coworking contract awaits countersignature

- **WHEN** a confirmed admin applies for coworking and signs online
- **THEN** the agreement's signed document expects two signatures and has one
- **AND** the agreement is shown to managers as awaiting countersignature

#### Scenario: Signed later

- **WHEN** an admin signs the contract of their submitted agreement online after applying
- **THEN** the agreement's signed document and date are set as with the application

#### Scenario: Kind without contract document

- **WHEN** a kind has no contract document with a current version
- **THEN** the application form offers only the upload

### Requirement: Authorized signatories

A manager SHALL be marked as authorized to countersign, with a signatory title. Only managers with the flag SHALL see the countersign action. The title SHALL be printed as function in the countersignature slot.

#### Scenario: Authorized manager

- **WHEN** a manager with the flag and the title "Managing director" countersigns
- **THEN** slot 2 shows the manager's name and "Managing director"

#### Scenario: Manager without flag

- **WHEN** a manager without the flag opens an agreement awaiting countersignature
- **THEN** no countersign action is offered and a direct request is denied

### Requirement: Countersignature approves the agreement

For kinds requiring a countersignature, an authorized manager within scope SHALL countersign a submitted agreement whose contract was signed online by the applicant and that has an active mandate. Countersigning SHALL add the second signature to the agreement's signed document, which completes and seals it, and approve the agreement with the signing date as decision date and the countersigning manager as deciding manager, with all effects of approval. Countersigning SHALL be refused when the applicant's signature is missing, the mandate is missing, the agreement is not submitted, or the manager is out of scope. A plain approval of an agreement whose signed document is not complete SHALL be refused with a pointer to the countersignature; an uploaded document SHALL be approved as before. Rejection SHALL remain available to any manager within scope. Kinds without countersignature SHALL keep the manager's recorded decision.

#### Scenario: Countersign and approve

- **WHEN** an authorized manager countersigns a submitted coworking agreement signed by the applicant and with an active mandate
- **THEN** the signed document is complete and sealed
- **AND** the agreement is active with the signing date as decision date and the manager as deciding manager
- **AND** the group is added, the code created because coworking grants one, and the decision email sent as on approval

#### Scenario: Countersign without mandate

- **WHEN** an authorized manager countersigns an agreement without an active mandate
- **THEN** the action is refused and nothing is signed

#### Scenario: Plain approval while awaiting countersignature

- **WHEN** a manager approves a coworking agreement whose signed document awaits a countersignature
- **THEN** the action is refused with a pointer to the countersignature

#### Scenario: Uploaded contract approved as before

- **WHEN** a manager approves a coworking agreement whose signed document was uploaded
- **THEN** the agreement is approved as before

#### Scenario: Membership approved by decision

- **WHEN** a manager approves a membership agreement signed online
- **THEN** the agreement is approved with the entered decision date and no countersignature is added

#### Scenario: Reject while awaiting countersignature

- **WHEN** a manager rejects an agreement awaiting countersignature
- **THEN** the agreement is rejected and its signed document stays with one signature

### Requirement: SEPA mandate can be signed online

The mandate form SHALL offer signing online as an alternative to uploading a signed mandate, with exactly one of the two. Signing online SHALL generate the mandate from the standard SEPA core mandate text with creditor name, creditor identifier, generated mandate reference, account holder, IBAN, BIC and bank name, and sign it with one signature using the agreement's contact person function. The signed PDF SHALL be stored as the mandate's signed document with the signing date, and the mandate SHALL be linked to the signed document. The mandate reference SHALL be generated before the PDF is rendered and SHALL appear on it.

#### Scenario: Mandate signed online

- **WHEN** a confirmed admin adds a mandate with valid bank data and signs online
- **THEN** an active mandate exists with the signed PDF as signed document and the signing date
- **AND** the PDF shows the mandate text, creditor identifier, mandate reference, account holder and IBAN

#### Scenario: Invalid IBAN signs nothing

- **WHEN** a mandate is submitted for online signing with an invalid IBAN
- **THEN** the form is invalid and no signed document is created

#### Scenario: Mandate uploaded

- **WHEN** a confirmed admin adds a mandate with an uploaded signed PDF
- **THEN** the mandate is created as before, with no signed document linked
