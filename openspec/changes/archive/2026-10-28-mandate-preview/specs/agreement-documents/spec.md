## ADDED Requirements

### Requirement: Prefilled mandate before saving

The mandate form SHALL offer a download of the generated mandate filled with the entered bank data and the reference the mandate will get when saved. The system SHALL validate the entered values like saving and show the form's errors instead of a document when they are invalid, and SHALL refuse the download where saving the mandate would be refused. The download SHALL NOT create a mandate and SHALL leave the entered values in the form.

#### Scenario: Download before saving

- **WHEN** an organization admin enters valid bank data on the mandate form of a submitted agreement and requests the prefilled mandate
- **THEN** the response is a PDF containing the account holder, the full IBAN and the reference the mandate gets when saved, and no mandate exists

#### Scenario: Invalid IBAN

- **WHEN** the admin requests the prefilled mandate with an invalid IBAN
- **THEN** the mandate form is shown again with the IBAN error and no document

#### Scenario: Closed agreement

- **WHEN** the agreement is ended or rejected
- **THEN** the prefilled mandate is refused like saving a mandate
