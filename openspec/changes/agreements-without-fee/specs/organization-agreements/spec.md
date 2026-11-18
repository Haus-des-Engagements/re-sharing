## ADDED Requirements

### Requirement: Agreements without a fee

An agreement's amount SHALL NOT be negative. Staff in the admin, the spreadsheet import and managers creating or editing an agreement in the frontend SHALL be able to enter an amount of zero, whatever the kind's minimum amount. The import SHALL treat an empty amount as zero. Applicants SHALL enter an amount above zero.

#### Scenario: Agreement without a fee imported

- **WHEN** staff import a row with the amount 0 for a kind with the minimum amount 60 €
- **THEN** the agreement is imported with the amount 0

#### Scenario: Empty amount imported

- **WHEN** staff import a row with an empty amount
- **THEN** the agreement is imported with the amount 0

#### Scenario: Negative amount

- **WHEN** staff import a row with the amount -5
- **THEN** the preview shows the error and nothing is imported

#### Scenario: Manager enters zero

- **WHEN** a manager creates or edits an agreement with the amount 0
- **THEN** the agreement is saved with the amount 0

#### Scenario: Applicant enters zero

- **WHEN** a member applies with the amount 0
- **THEN** the form is rejected with a message that the amount must be above zero
