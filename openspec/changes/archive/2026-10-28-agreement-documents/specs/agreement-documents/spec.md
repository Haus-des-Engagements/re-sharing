## ADDED Requirements

### Requirement: Contract template per kind

An agreement kind SHALL optionally carry a contract template, a fillable PDF uploaded in the admin and kept in private storage. The admin SHALL list the template's form fields and mark which of them the system fills.

#### Scenario: Template uploaded

- **WHEN** staff upload a fillable PDF as a kind's contract template
- **THEN** the kind's admin page lists its field names, marking `organization_name` as filled and an unknown name such as `place_date` as left empty

#### Scenario: Non-PDF refused

- **WHEN** staff upload a file that is not a PDF as contract template
- **THEN** the admin rejects it

### Requirement: Prefilled contract

The system SHALL offer the organization's confirmed admins and managers in scope a download of the kind's contract template filled with the agreement's data while the agreement is submitted or active. Form fields SHALL be filled by name: organization name, address, phone, email and website; a ticked representation checkbox; representative name, function and email; amount, start date, end date and deposit formatted in German; the kind's name; and the answers of the kind's application fields under `detail_<key>`. Other fields SHALL stay empty, and all fields SHALL stay editable. The representative SHALL be the agreement's contact person, or without one the downloading organization admin. The document SHALL be generated on request and not stored.

#### Scenario: Applicant downloads the prefilled contract

- **WHEN** the admin who applied for a membership with 80 € opens the prefilled contract
- **THEN** the PDF contains the organization's name, address, phone, email and website, the admin's name and email, the function from the application and the amount `80,00`

#### Scenario: Kind without template

- **WHEN** an agreement's kind has no contract template
- **THEN** the agreement page offers no prefilled contract and the download returns not found

#### Scenario: Closed agreement

- **WHEN** an agreement is ended or rejected
- **THEN** the prefilled contract is no longer offered

#### Scenario: Other users

- **WHEN** a booker of the organization or a manager out of scope requests the prefilled contract
- **THEN** access is denied

### Requirement: Generated SEPA mandate

The system SHALL generate the SEPA mandate as a separate PDF containing the creditor's name, address and identifier, the mandate reference, the standard wording of a recurring core direct debit mandate including the refund notice, the agreement's kind, the debtor organization and its address, account holder, bank, IBAN, BIC, and lines for place, date and signature. The mandate page SHALL offer it for download to those who may see the mandate, as long as it is not revoked. It SHALL be generated on request, not stored, and never attached to emails.

#### Scenario: Mandate downloaded before signing

- **WHEN** an organization admin opens the mandate document of a mandate saved without signed PDF
- **THEN** the PDF contains the mandate reference, the creditor identifier, the account holder and the full IBAN

#### Scenario: Revoked mandate

- **WHEN** a mandate is revoked
- **THEN** its mandate document is no longer offered

#### Scenario: Other users

- **WHEN** a booker of the organization requests the mandate document
- **THEN** access is denied
