## ADDED Requirements

### Requirement: Prefilled contract before applying

The application page of a kind with a contract template SHALL offer a download of the contract prefilled with the values entered in the application form, the organization's data and the applying admin as representative. The system SHALL validate the entered values like a submission and show the form's errors instead of a document when they are invalid. The download SHALL NOT create an agreement or send emails, and SHALL leave the entered values in the form.

#### Scenario: Download before submitting

- **WHEN** an organization admin enters 80 € and the function "Board" on the membership application and requests the prefilled contract
- **THEN** the response is a PDF containing the organization's name, the admin's name, "Board" and the amount `80,00`, and no agreement exists

#### Scenario: Invalid input

- **WHEN** the admin requests the prefilled contract with an amount below the kind's minimum
- **THEN** the application form is shown again with the amount error and no document

#### Scenario: Kind without template

- **WHEN** the kind has no contract template
- **THEN** the application page offers no prefilled contract download and a preview request returns not found
