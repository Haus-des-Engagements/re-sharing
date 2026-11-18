## ADDED Requirements

### Requirement: Signing input

Forms that offer online signing SHALL ask for the typed name and a drawn signature, and SHALL show a sentence stating that the signer has read the document and may sign on behalf of the named party. Name and drawing SHALL be required together. A drawing that is not a PNG image or exceeds 200 KB SHALL be refused. A form SHALL refuse a drawn signature together with an uploaded PDF. The signer's function SHALL be taken from the data the form or the agreement already holds.

#### Scenario: Name and drawing accepted

- **WHEN** a user submits a typed name and a drawn signature
- **THEN** the form is valid

#### Scenario: Drawing without name

- **WHEN** a user submits a drawn signature without a name
- **THEN** the form is invalid and nothing is signed

#### Scenario: Not an image

- **WHEN** the submitted drawing is not a PNG image
- **THEN** the form is invalid and nothing is signed

#### Scenario: Upload and signature

- **WHEN** a user submits an uploaded PDF and a drawn signature
- **THEN** the form is invalid with a message to choose one

### Requirement: Signature page

Signing SHALL produce a PDF consisting of the unchanged source pages followed by one signature page. The page SHALL show the document name, the party signed for, the drawn signature, the typed name, the function, date and time in Europe/Berlin, and the email address of the account that signed. The result SHALL be stored in the file field an upload would fill, with the day of signing as signing date. Signing a PDF that already ends with a signature page SHALL append a further page.

#### Scenario: Page appended

- **WHEN** a user signs a three-page document
- **THEN** the stored PDF has four pages, the first three those of the source
- **AND** the fourth shows the signer's name, function, party, account and signing time

#### Scenario: Second signature

- **WHEN** a PDF that ends with a signature page is signed again
- **THEN** the stored PDF has one more page and the earlier pages are unchanged

### Requirement: Agreement contract signed online

For kinds with a contract template, the application form and the signed document form SHALL offer online signing next to the upload. Signing SHALL use the contract prefilled with the agreement's data and the signer as representative, as described in `agreement-documents`, on behalf of the organization and with the agreement's contact person function. The result SHALL be the agreement's signed document. Signing after applying SHALL be offered while the agreement is submitted. Kinds without a template SHALL offer only the upload, and the manager forms for entering agreements SHALL NOT offer signing.

#### Scenario: Signed with the application

- **WHEN** a confirmed member applies for a membership with 80 € and the function "Board" and signs online
- **THEN** the agreement's signed document is the prefilled contract with the amount `80,00` followed by a signature page naming the member, "Board" and the organization
- **AND** its signing date is today

#### Scenario: Signed later

- **WHEN** a member signs the contract of a submitted agreement without signed document online
- **THEN** the agreement has a signed document and signing date as with the application

#### Scenario: Active agreement

- **WHEN** a member opens the signed document form of an active agreement
- **THEN** it offers only the upload

#### Scenario: Applied without signing

- **WHEN** a member applies with neither upload nor signature
- **THEN** the agreement is created without signed document, as before

#### Scenario: Kind without template

- **WHEN** a kind has no contract template
- **THEN** its application form offers only the upload

### Requirement: SEPA mandate signed online

The mandate form and the signed mandate form SHALL offer online signing next to the upload. Signing SHALL use the generated mandate with its reference and bank data, on behalf of the organization and with the agreement's contact person function. The result SHALL be the mandate's signed document, which makes the mandate active.

#### Scenario: Signed when saving

- **WHEN** a member saves valid bank data and signs online
- **THEN** an active mandate exists whose signed document shows the mandate reference, the creditor identifier and the full IBAN, followed by a signature page

#### Scenario: Signed later

- **WHEN** a member signs a mandate saved without signed PDF online from its page
- **THEN** the mandate is active with the signed PDF and today's signing date

#### Scenario: Invalid IBAN

- **WHEN** a mandate is submitted with a signature and an invalid IBAN
- **THEN** the form is invalid and no mandate exists

### Requirement: Countersignature on approval

An agreement kind SHALL optionally require a countersignature, and a manager SHALL optionally carry a signatory title. Approving an agreement of such a kind SHALL require a manager with a signatory title and that manager's online signature, in addition to the existing conditions. Approval SHALL then append a signature page on behalf of the operator with the manager's name and title to the agreement's signed document, whether that document was signed online or uploaded. Rejection SHALL remain open to every manager within scope. Kinds without the requirement SHALL be approved as before.

#### Scenario: Approve and countersign

- **WHEN** a manager with the title "Managing director" approves a submitted coworking agreement with signed contract and active mandate, signing in the approval form
- **THEN** the agreement is active with all effects of approval
- **AND** its signed document ends with a page showing the manager's name, "Managing director" and the operator

#### Scenario: Manager without title

- **WHEN** a manager without signatory title approves a coworking agreement
- **THEN** the approval is refused and the signed document is unchanged

#### Scenario: Approval without signature

- **WHEN** a manager with a title approves a coworking agreement without signing
- **THEN** the approval is refused and the signed document is unchanged

#### Scenario: Uploaded contract

- **WHEN** a manager with a title approves and signs a coworking agreement whose contract was uploaded
- **THEN** the uploaded PDF is followed by the manager's signature page and the agreement is active

#### Scenario: Kind without countersignature

- **WHEN** a manager approves a membership agreement
- **THEN** it is approved as before and its signed document is unchanged

#### Scenario: Rejection

- **WHEN** a manager without signatory title rejects a coworking agreement
- **THEN** the agreement is rejected

### Requirement: Registration document signed online

When the registration document has a current version with a file, the organization creation form SHALL offer online signing next to the upload, together with a field for the signer's function. Exactly one of the two SHALL be provided. With a signature, the system SHALL sign that file on behalf of the new organization, named with its address, and store the result as the organization's registration document with today's date. Without such a file the form SHALL offer only the upload.

#### Scenario: Registration signed online

- **WHEN** a user creates an organization signing online with name, function and drawing
- **THEN** the organization's registration document is the current version's PDF followed by a signature page naming the user, the function and the organization with its address
- **AND** its registration document date is today

#### Scenario: Registration uploaded

- **WHEN** a user creates an organization with an uploaded PDF and signing date
- **THEN** the organization is created as before

#### Scenario: Neither upload nor signature

- **WHEN** a user submits the creation form with neither an upload nor a signature
- **THEN** the form is invalid

#### Scenario: No file to sign

- **WHEN** the registration document has no current version with a file
- **THEN** the creation form offers only the upload

### Requirement: Signing by hand stays possible

Every form that offers online signing SHALL keep its upload of a hand-signed PDF. While the agreement is submitted, an upload SHALL replace a stored document, including one signed online.

#### Scenario: Upload after online signature

- **WHEN** a member uploads a hand-signed contract for a submitted agreement whose contract was signed online
- **THEN** the agreement's signed document is the uploaded file with the entered signing date

### Requirement: Signed documents of decided agreements

Once an agreement is no longer submitted, members of the organization SHALL NOT replace its stored signed contract or a stored signed mandate; only a manager within scope SHALL. Members SHALL still provide a signed contract or signed mandate that is missing. The agreement page SHALL show a stored contract's form collapsed behind a replace action, and only to those who may replace it.

#### Scenario: Member replaces the contract of an active agreement

- **WHEN** a member uploads a PDF for an active agreement that has a signed contract
- **THEN** the upload is refused with a message naming the manager, and the stored contract is unchanged

#### Scenario: Manager replaces the contract of an active agreement

- **WHEN** a manager within scope uploads a PDF for an active agreement that has a signed contract
- **THEN** the uploaded file is the agreement's signed document

#### Scenario: Member replaces the mandate of an active agreement

- **WHEN** a member uploads a PDF for the signed mandate of an active agreement
- **THEN** the upload is refused and the stored mandate is unchanged

#### Scenario: New mandate of an active agreement

- **WHEN** a member signs or uploads a mandate that was saved without signed PDF for an active agreement
- **THEN** the mandate is active

#### Scenario: Replace action on the agreement page

- **WHEN** a member opens a submitted agreement that has a signed contract
- **THEN** the page shows a replace action instead of the open form
- **AND** on an active agreement the member sees neither
