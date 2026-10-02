## ADDED Requirements

### Requirement: Agreement kinds are configuration

The system SHALL provide an agreement kind model edited by staff in the admin. A kind SHALL define the organization group it grants, a billing interval of yearly or monthly, the allowed payment methods, whether a deposit is required, a notice period, whether an end date is required, the entrances granted on approval, whether every collection is pre-notified, the collection day, an intro text and an active flag.

#### Scenario: Inactive kind is not offered

- **WHEN** a kind has its active flag unset
- **THEN** it is not offered on the application page

#### Scenario: Kind restricts payment methods

- **WHEN** a kind allows only direct debit
- **THEN** the application form for that kind offers no bank transfer option

### Requirement: Confirmed organization admins can apply

The system SHALL allow a user with a confirmed admin booking permission on an organization with status `Confirmed` to submit an application for an active kind. An application SHALL record amount, start date, payment method, and the kind-specific details; the agreement SHALL have status `Submitted`. The system SHALL reject applications from users without an admin permission, for organizations that are not confirmed, and for kinds for which the organization already has a submitted or active agreement.

#### Scenario: Successful application

- **WHEN** a confirmed admin of a confirmed organization submits a valid application for an active kind
- **THEN** an agreement with status `Submitted` is created for that organization and kind
- **AND** the organization and the responsible managers receive an application email

#### Scenario: Organization not confirmed

- **WHEN** an admin of a pending organization opens the application page
- **THEN** the action is denied

#### Scenario: Booker without admin role

- **WHEN** a user with a booker permission submits an application
- **THEN** the action is denied

#### Scenario: Duplicate application for the same kind

- **WHEN** an organization already has a submitted or active agreement of a kind and applies for it again
- **THEN** the form is rejected with a message naming the existing agreement

#### Scenario: Kind-specific details are stored

- **WHEN** a coworker application is submitted with a number of desks and hours per week
- **THEN** both values are stored in the agreement's details and shown on the agreement page

### Requirement: Manager records the board decision

The system SHALL allow a manager within scope to approve or reject a submitted agreement, recording a decision date. Approval SHALL require a signed document on the agreement and, for direct debit, an active mandate. Approving or rejecting an agreement that is not submitted SHALL be refused. Non-managers SHALL be denied.

#### Scenario: Approve a submitted agreement

- **WHEN** a manager approves a submitted agreement with a signed document and, for direct debit, an active mandate, entering a decision date
- **THEN** the agreement status becomes `Active` with the decision date and deciding manager stored
- **AND** the organization receives a decision email

#### Scenario: Approval without signed document

- **WHEN** a manager approves a submitted agreement that has no signed document
- **THEN** the approval is refused with a message naming the missing document

#### Scenario: Approval of direct debit agreement without mandate

- **WHEN** a manager approves a submitted direct debit agreement without an active mandate
- **THEN** the approval is refused with a message naming the missing mandate

#### Scenario: Reject a submitted agreement

- **WHEN** a manager rejects a submitted agreement entering a decision date
- **THEN** the agreement status becomes `Rejected`
- **AND** the organization receives a decision email
- **AND** no group or code is granted

#### Scenario: Decision on an active agreement

- **WHEN** a manager tries to approve or reject an active agreement
- **THEN** the action is refused

#### Scenario: Manager outside scope

- **WHEN** a manager scoped to groups that do not include the kind's group opens the agreement
- **THEN** the action is denied

### Requirement: Approval grants group and entrance code

On approval the system SHALL add the kind's organization group to the organization, SHALL create a permanent code for the organization with exactly the kind's accesses, SHALL store that code on the agreement, and SHALL create a deposit collection when the kind requires a deposit.

#### Scenario: Group added on approval

- **WHEN** an agreement whose kind grants group G is approved
- **THEN** the organization is a member of group G

#### Scenario: Permanent code with kind accesses

- **WHEN** an agreement whose kind lists accesses A and B is approved
- **THEN** a permanent code with validity start now and accesses exactly A and B exists for the organization
- **AND** the permanent code created email is sent

#### Scenario: Deposit collection created

- **WHEN** an agreement whose kind requires a deposit is approved with a deposit amount
- **THEN** a deposit collection with that amount and the agreement's start date as due date exists

#### Scenario: No deposit for kinds without one

- **WHEN** an agreement whose kind requires no deposit is approved
- **THEN** no deposit collection exists

### Requirement: Ending an agreement

The system SHALL allow a manager to end an active agreement. Ending SHALL set the end date to today if empty, SHALL remove the kind's group unless another active agreement of the organization grants the same group, SHALL set the validity end of the permanent code created by this agreement to the end date, SHALL cancel planned collections with a period start after the end date, SHALL create a deposit refund record when a paid deposit exists, and SHALL send an ended email. A daily command SHALL end active agreements whose end date has passed.

#### Scenario: Manager ends an agreement

- **WHEN** a manager ends an active agreement with no end date
- **THEN** the status becomes `Ended` with today as end date
- **AND** the organization is no longer in the kind's group
- **AND** the agreement's permanent code has a validity end
- **AND** planned collections for later periods are cancelled

#### Scenario: Group kept for another active agreement

- **WHEN** an organization has two active agreements granting the same group and one is ended
- **THEN** the organization remains in the group

#### Scenario: Deposit refund record

- **WHEN** an agreement with a paid deposit is ended
- **THEN** a deposit refund collection with the deposit amount exists in status `Planned`

#### Scenario: Expired end date

- **WHEN** the daily command runs and an active agreement has an end date before today
- **THEN** the agreement is ended as if by a manager

### Requirement: Agreement visibility

The system SHALL show an organization's agreements, with status, amount, payment method and collections, to its confirmed users. Managers SHALL see a list of agreements filterable by kind and status within their scope, with a count of submitted agreements. Other users SHALL be denied.

#### Scenario: Organization user sees own agreements

- **WHEN** a confirmed user of an organization opens the organization's agreements page
- **THEN** all agreements of that organization are listed with their collections

#### Scenario: Foreign user denied

- **WHEN** a user without a confirmed permission on the organization opens its agreements page
- **THEN** the action is denied

#### Scenario: Manager list filtered by status

- **WHEN** a manager filters the agreement list by `Submitted`
- **THEN** only submitted agreements of kinds within the manager's scope are listed
