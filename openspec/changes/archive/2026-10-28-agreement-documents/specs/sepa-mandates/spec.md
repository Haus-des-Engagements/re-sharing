## MODIFIED Requirements

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
