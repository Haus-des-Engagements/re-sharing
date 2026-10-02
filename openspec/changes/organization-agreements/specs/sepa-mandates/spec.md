## ADDED Requirements

### Requirement: One active mandate per direct debit agreement

The system SHALL allow a mandate to be added to an agreement with payment method direct debit, capturing account holder, IBAN, BIC, bank name, signature date and the signed mandate PDF. At most one non-revoked mandate SHALL exist per agreement. Agreements with payment method bank transfer SHALL NOT accept a mandate.

#### Scenario: Applicant adds a mandate

- **WHEN** a confirmed admin of the organization adds a mandate with valid bank data and a signed PDF to a submitted direct debit agreement
- **THEN** an active mandate exists for the agreement

#### Scenario: Second active mandate refused

- **WHEN** a mandate is added to an agreement that already has a non-revoked mandate
- **THEN** the action is refused with a message pointing to revoking the existing mandate

#### Scenario: Mandate on transfer agreement refused

- **WHEN** a mandate is added to an agreement with payment method bank transfer
- **THEN** the action is refused

### Requirement: Mandate reference is generated

The system SHALL generate the mandate reference from a configured prefix, the agreement id padded to six digits and a running number per agreement. The reference SHALL be unique. References entered through the admin for existing paper mandates SHALL be accepted when unique, and the generator SHALL never produce a reference that already exists.

#### Scenario: First mandate reference

- **WHEN** the first mandate for agreement 42 is created with prefix `HDE`
- **THEN** its reference is `HDE-000042-1`

#### Scenario: Replacement mandate reference

- **WHEN** a second mandate is created for agreement 42 after the first was revoked
- **THEN** its reference is `HDE-000042-2`

#### Scenario: Duplicate reference entered in the admin

- **WHEN** staff enter a reference that already exists on another mandate
- **THEN** the form is rejected

### Requirement: Bank data validation and protection

The system SHALL validate the IBAN format and checksum and store it without spaces. The IBAN SHALL be rendered masked except on the manager's mandate detail, SHALL be excluded from audit log diffs, and SHALL NOT appear in emails. Signed mandate PDFs SHALL be stored in private storage and validated as PDF.

#### Scenario: Invalid IBAN

- **WHEN** a mandate is submitted with an IBAN whose checksum is wrong
- **THEN** the form is rejected with an IBAN error

#### Scenario: Masked display

- **WHEN** an organization user views a mandate
- **THEN** only the last four characters of the IBAN are shown

#### Scenario: Audit log excludes IBAN

- **WHEN** a mandate's IBAN is changed
- **THEN** the audit log entry does not contain the old or new IBAN

#### Scenario: Non-PDF upload

- **WHEN** a mandate is submitted with a non-PDF file as signed document
- **THEN** the form is rejected

### Requirement: Revocation

The system SHALL allow a manager to revoke a mandate, recording the revocation date. A revoked mandate SHALL NOT be used for new collections. Collections already submitted in a run SHALL keep their mandate snapshot.

#### Scenario: Revoke a mandate

- **WHEN** a manager revokes the active mandate of an agreement
- **THEN** the mandate has a revocation date
- **AND** a new collection for the agreement cannot be added to a run until a new mandate exists

#### Scenario: Submitted collection keeps mandate

- **WHEN** a mandate is revoked after a collection using it was submitted in a run
- **THEN** that collection still references the revoked mandate
