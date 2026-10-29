# sepa-mandates Specification

## Purpose
TBD - created by archiving change organization-agreements. Update Purpose after archive.
## Requirements
### Requirement: One active mandate per agreement

The system SHALL allow a mandate to be added to an agreement, capturing account holder, IBAN, BIC and bank name, and the signed mandate PDF with its signature date either at once or later. A mandate SHALL be active when it has a signed PDF and is not revoked. At most one non-revoked mandate SHALL exist per agreement. A mandate without signed PDF SHALL show its reference and bank data on its page together with a download of the generated mandate document, prefilled with reference and bank data as described in `agreement-documents`, and an upload for the signed PDF.

#### Scenario: Applicant adds a mandate

- **WHEN** a confirmed admin of the organization adds a mandate with valid bank data and a signed PDF to a submitted agreement
- **THEN** an active mandate exists for the agreement

#### Scenario: Mandate saved before signing

- **WHEN** a confirmed admin adds a mandate with valid bank data and no signed PDF
- **THEN** a mandate with a generated reference exists and is not active
- **AND** its page shows the reference, a download of the prefilled mandate document and an upload

#### Scenario: Signed mandate uploaded later

- **WHEN** the admin uploads the signed PDF with its signature date to that mandate
- **THEN** the mandate is active

#### Scenario: Second active mandate refused

- **WHEN** a mandate is added to an agreement that already has a non-revoked mandate
- **THEN** the action is refused with a message pointing to revoking the existing mandate

### Requirement: Mandate reference is generated

The system SHALL generate the mandate reference from a configured prefix and a running number across all mandates, padded to three digits, continuing after the highest number of the references in the database that consist of the prefix, a hyphen and digits. The reference SHALL be unique. References entered through the admin for existing paper mandates SHALL be accepted when unique, and the generator SHALL never produce a reference that already exists.

#### Scenario: Numbering continues after existing mandates

- **WHEN** mandates `HDE-VM-007` and `HDE-VM-008` exist and a new mandate is created with prefix `HDE-VM`
- **THEN** its reference is `HDE-VM-009`

#### Scenario: First mandate reference

- **WHEN** no reference with prefix `HDE-VM` exists and a mandate is created
- **THEN** its reference is `HDE-VM-001`

#### Scenario: Other formats ignored

- **WHEN** only the reference `HDE-000042-1` exists and a mandate is created with prefix `HDE-VM`
- **THEN** its reference is `HDE-VM-001`

#### Scenario: Duplicate reference entered in the admin

- **WHEN** staff enter a reference that already exists on another mandate
- **THEN** the form is rejected

### Requirement: Bank data validation and protection

The system SHALL validate the IBAN format and checksum and store it without spaces. The IBAN SHALL be rendered masked on pages except the manager's mandate detail, SHALL be excluded from audit log diffs, and SHALL NOT appear in emails. Signed mandate PDFs SHALL be stored in private storage, validated as PDF, and downloadable from the mandate page by the organization's admins and managers in scope; the PDF carries the full IBAN.

#### Scenario: Invalid IBAN

- **WHEN** a mandate is submitted with an IBAN whose checksum is wrong
- **THEN** the form is rejected with an IBAN error

#### Scenario: Masked display

- **WHEN** an organization user views a mandate
- **THEN** only the last four characters of the IBAN are shown

#### Scenario: Audit log excludes IBAN

- **WHEN** a mandate's IBAN is changed
- **THEN** the audit log entry does not contain the old or new IBAN

#### Scenario: Signed mandate download

- **WHEN** a confirmed admin of the organization downloads the signed mandate from the mandate page
- **THEN** the PDF is served from private storage
- **AND** a user without a confirmed permission on the organization is denied

#### Scenario: Non-PDF upload

- **WHEN** a mandate is submitted with a non-PDF file as signed document
- **THEN** the form is rejected

### Requirement: Revocation

The system SHALL allow a manager to revoke a mandate, recording the revocation date. A revoked mandate SHALL NOT be used for new runs. Collections already submitted in a run SHALL keep their mandate.

#### Scenario: Revoke a mandate

- **WHEN** a manager revokes the active mandate of an agreement
- **THEN** the mandate has a revocation date
- **AND** notified collections of the agreement are excluded from runs until a new mandate exists

#### Scenario: Submitted collection keeps mandate

- **WHEN** a mandate is revoked after a collection using it was submitted in a run
- **THEN** that collection still references the revoked mandate

### Requirement: Mandate file names

Signed mandate PDFs SHALL be stored and downloaded under the name `<reference>_SEPA-Lastschriftmandat_<organization>_<signature date as YYYY-MM-DD>.pdf`, and the generated mandate SHALL download under the same name with the download date. The organization's name SHALL appear without dots and without characters invalid in file names.

#### Scenario: Signed mandate uploaded

- **WHEN** the signed PDF of mandate `HDE-VM-008` of `Example e.V.` signed on 2024-04-15 is uploaded
- **THEN** it is stored as `HDE-VM-008_SEPA-Lastschriftmandat_Example eV_2024-04-15.pdf`

#### Scenario: Generated mandate downloaded

- **WHEN** an admin downloads the generated mandate `HDE-VM-009` on 2026-10-28
- **THEN** the file is named `HDE-VM-009_SEPA-Lastschriftmandat_<organization>_2026-10-28.pdf`

### Requirement: Mandate import

The admin SHALL offer a spreadsheet import of mandates with agreement id, reference, account holder, IBAN, BIC, bank name, signature date and revocation date, without signed PDFs. Rows SHALL be validated like the admin form, including IBAN checksum, unique reference and one non-revoked mandate per agreement, and the import SHALL only be offered after a preview without errors. The admin SHALL NOT offer an export of mandates. Imported mandates SHALL count as active only once their signed PDF is uploaded.

#### Scenario: Paper mandate imported

- **WHEN** staff import a row with reference `HDE-VM-008`, an IBAN written with spaces and signature date 2024-04-15
- **THEN** a mandate with that reference and the IBAN without spaces exists and is not active

#### Scenario: Invalid row

- **WHEN** a row has an invalid IBAN or a reference that already exists
- **THEN** the preview shows the error and nothing is imported

#### Scenario: Numbering after the import

- **WHEN** mandates up to `HDE-VM-008` were imported and a new mandate is created
- **THEN** its reference is `HDE-VM-009`

#### Scenario: No export

- **WHEN** staff open the mandate list in the admin
- **THEN** no export is offered

