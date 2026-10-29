## ADDED Requirements

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
