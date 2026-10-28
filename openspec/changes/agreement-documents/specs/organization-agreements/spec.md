## MODIFIED Requirements

### Requirement: Signed document

An agreement SHALL carry a signed document (PDF, private storage) with its signing date, provided by the applicant with the application or afterwards, or by a manager. The application page SHALL show the kind's intro text. An agreement SHALL record the applicant as its contact person. Where the kind has a contract template, the agreement page SHALL offer the contract prefilled with the agreement's data as described in `agreement-documents`. An uploaded document SHALL count as complete. Approval SHALL require a complete signed document.

#### Scenario: Contract download

- **WHEN** an admin opens the application page of a kind
- **THEN** the kind's intro text is shown

#### Scenario: Upload after application

- **WHEN** an admin uploads a signed PDF with a signing date to their submitted agreement
- **THEN** the document and date are stored on the agreement

#### Scenario: Non-PDF rejected

- **WHEN** a non-PDF file is uploaded as signed document
- **THEN** the form is rejected

#### Scenario: Contact person recorded

- **WHEN** an admin submits an application
- **THEN** the agreement records that admin as its contact person
