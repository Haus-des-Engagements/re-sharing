## ADDED Requirements

### Requirement: Agreements without a fee are not collected

The system SHALL NOT create fee collections for an agreement whose amount is zero, neither for regular periods nor for the prorated first period at approval.

#### Scenario: Regular periods

- **WHEN** the command runs for an active monthly agreement with the amount 0
- **THEN** no fee collection is created for it

#### Scenario: First period at approval

- **WHEN** a membership with the amount 0 starting 2027-10-10 is approved
- **THEN** no fee collection for the rest of the year is created
