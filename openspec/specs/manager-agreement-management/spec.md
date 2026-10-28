# manager-agreement-management Specification

## Purpose
TBD - created by archiving change agreement-fields-and-manager-agreements. Update Purpose after archive.
## Requirements
### Requirement: Managers create agreements

A manager SHALL be able to create an agreement in the frontend for a confirmed organization and an active kind within the manager's scope, whether or not the kind accepts applications. The manager SHALL first choose the kind, then fill the organization, the status `Submitted` or `Active`, the common agreement data, the kind's fields and optionally the signed document and notes. The system SHALL refuse kinds outside the manager's scope, inactive kinds, organizations that are not confirmed and an organization that already has a submitted or active agreement of the kind. Creating SHALL NOT send emails. The kind's minimum amount SHALL NOT bind managers, so that existing agreements with lower amounts can be entered; it is shown as a hint.

#### Scenario: Submitted agreement from a paper application

- **WHEN** a manager creates a submitted coworking agreement for a confirmed organization
- **THEN** the agreement has status `Submitted`, no email is sent, and it follows the normal mandate and decision flow

#### Scenario: Existing member entered as active

- **WHEN** a manager creates an active membership agreement with a decision date for a confirmed organization that is not yet in the member group
- **THEN** the agreement has status `Active` with that decision date and the manager as decider
- **AND** the organization is added to the member group
- **AND** no entrance code, deposit collection or first-period collection is created

#### Scenario: Billing of an agreement entered as active

- **WHEN** an active agreement is entered by a manager
- **THEN** the daily job creates collections only for periods due after the agreement was created

#### Scenario: Amount below the minimum entered by a manager

- **WHEN** a manager creates or edits an agreement with an amount below the kind's minimum amount
- **THEN** the agreement is saved with that amount

#### Scenario: Kind outside scope

- **WHEN** a manager opens the create form for a kind whose group is outside their scope
- **THEN** access is denied

#### Scenario: Duplicate agreement

- **WHEN** a manager creates an agreement of a kind the organization already holds as submitted or active
- **THEN** the form is rejected with a message naming the existing agreement

#### Scenario: Preselected organization

- **WHEN** a manager starts creating an agreement from an organization's page
- **THEN** the create form has that organization preselected

#### Scenario: Non-manager

- **WHEN** a user who is not a manager opens the create form
- **THEN** access is denied

### Requirement: Managers edit agreements

A manager within scope SHALL be able to edit a submitted or active agreement: start date, end date, amount, deposit amount, contact person function, notes and the answers to the kind's active fields, validated as in the application. Status, kind and organization SHALL NOT be editable. Collections created before the edit SHALL keep their amount, period and due date. Edits SHALL be recorded in the audit log with the manager as actor.

#### Scenario: Amount changed

- **WHEN** a manager changes the amount of an active agreement that already has a planned collection
- **THEN** the planned collection keeps its amount and the next collection created uses the new amount

#### Scenario: Closed agreement

- **WHEN** a manager opens the edit form of an ended or rejected agreement
- **THEN** the edit is refused

#### Scenario: End date before start

- **WHEN** a manager enters an end date that is not after the start date
- **THEN** the form is rejected

### Requirement: Managers delete untouched agreements

A manager within scope SHALL be able to delete a submitted agreement without collections after confirming on a page that lists what is removed. Deleting SHALL remove the agreement, its mandates and their stored documents. Every other agreement SHALL NOT be deletable; it is rejected or ended instead. The admin SHALL apply the same rule.

#### Scenario: Submitted agreement deleted

- **WHEN** a manager confirms deleting a submitted agreement with a mandate and a signed contract
- **THEN** the agreement, the mandate and both stored documents are gone

#### Scenario: Active agreement

- **WHEN** a manager tries to delete an active agreement
- **THEN** the deletion is refused with a hint to end it instead

#### Scenario: Agreement with collections

- **WHEN** an agreement has any collection
- **THEN** neither the frontend nor the admin offers deleting it

