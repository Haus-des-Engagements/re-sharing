# organization-agreements Specification

## Purpose
TBD - created by archiving change organization-agreements. Update Purpose after archive.
## Requirements
### Requirement: Agreement kinds are configuration

The system SHALL provide an agreement kind model edited by staff in the admin. A kind SHALL define the organization group it grants, a billing interval of yearly or monthly, whether a deposit is required, a notice period, whether an end date is required, an optional minimum amount, the entrances granted on approval (none for kinds without an entrance code), a notification mode of per collection or once at approval, the collection day, for yearly kinds the collection month, an intro text shown on the application page, its application fields, an active flag and an accepting-applications flag. Kinds SHALL NOT be editable outside the admin. A kind with agreements SHALL NOT be deletable; it is deactivated instead.

#### Scenario: Kind not accepting applications is hidden

- **WHEN** a kind has its accepting-applications flag unset
- **THEN** it is not offered on the application page
- **AND** managers can still create agreements of that kind

#### Scenario: Inactive kind

- **WHEN** a kind has its active flag unset
- **THEN** it is not offered on the application page, managers cannot create agreements of it, and no new collections are created for its agreements

#### Scenario: Kind in use cannot be deleted

- **WHEN** staff try to delete a kind that has agreements in the admin
- **THEN** the deletion is not offered

### Requirement: Organization admins can apply

The system SHALL allow a user with a confirmed admin booking permission on an organization with status `Confirmed` to submit an application for a kind that is active and accepting applications. An application SHALL record start date, an amount not below the kind's minimum amount where one is set, the answers to the kind's active application fields and SHALL have status `Submitted`. The system SHALL reject applications from users without an admin permission, for organizations that are not confirmed, and for kinds for which the organization already has a submitted or active agreement. The organization page SHALL show the open kinds as available actions.

#### Scenario: Confirmed organization applies

- **WHEN** a confirmed admin of a confirmed organization submits a valid membership application
- **THEN** an agreement with status `Submitted` is created
- **AND** the organization and the responsible managers receive an application email

#### Scenario: Pending organization

- **WHEN** an admin of a pending organization opens the application page
- **THEN** the action is denied with a hint that the organization must be confirmed first

#### Scenario: Deactivated organization

- **WHEN** an admin of a deactivated organization opens the application page
- **THEN** the action is denied

#### Scenario: Booker without admin role

- **WHEN** a user with a booker permission submits an application
- **THEN** the action is denied

#### Scenario: Duplicate application for the same kind

- **WHEN** an organization already has a submitted or active agreement of a kind and applies for it again
- **THEN** the form is rejected with a message naming the existing agreement

#### Scenario: Amount below the minimum

- **WHEN** a kind has the minimum amount 60 € and an admin applies with 40 €
- **THEN** the form is rejected with a message naming the minimum
- **AND** the amount field shows the minimum as a hint

#### Scenario: Kind-specific details are stored

- **WHEN** a coworking kind defines the fields desks and hours per week and an application is submitted with both
- **THEN** both values are stored in the agreement's details under their keys and shown on the agreement page with their labels

### Requirement: Signed document

An agreement SHALL carry a signed document (PDF, private storage) with its signing date, provided by the applicant with the application or afterwards, or by a manager. The application page SHALL show the kind's intro text, which links the contract to download. An uploaded document SHALL count as complete. Approval SHALL require a complete signed document.

#### Scenario: Contract download

- **WHEN** an admin opens the application page of a kind
- **THEN** the kind's intro text with the link to the contract is shown

#### Scenario: Upload after application

- **WHEN** an admin uploads a signed PDF with a signing date to their submitted agreement
- **THEN** the document and date are stored on the agreement

#### Scenario: Non-PDF rejected

- **WHEN** a non-PDF file is uploaded as signed document
- **THEN** the form is rejected

### Requirement: Manager records the board decision

The system SHALL allow a manager within scope to approve or reject a submitted agreement, recording a decision date. Approval SHALL require a complete signed document and an active mandate. Deciding on an agreement that is not submitted SHALL be refused. Non-managers SHALL be denied. Agreement decisions SHALL NOT change the organization status.

#### Scenario: Approve a submitted agreement

- **WHEN** a manager approves a submitted agreement that has a complete signed document and an active mandate, entering a decision date
- **THEN** the agreement status becomes `Active` with decision date and deciding manager stored
- **AND** the organization receives a decision email
- **AND** the organization status is unchanged

#### Scenario: Approval without signed document

- **WHEN** a manager approves a submitted agreement that has no signed document
- **THEN** the approval is refused with a message naming the missing document

#### Scenario: Approval without mandate

- **WHEN** a manager approves a submitted agreement without an active mandate
- **THEN** the approval is refused with a message naming the missing mandate

#### Scenario: Approval with mandate awaiting its signed PDF

- **WHEN** a manager approves a submitted agreement whose mandate was saved without a signed PDF
- **THEN** the approval is refused with a message naming the missing signed mandate

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

On approval the system SHALL add the kind's organization group to the organization, SHALL create a permanent code with exactly the kind's accesses when the kind has any and store it on the agreement, SHALL create a deposit collection when the kind requires a deposit, and SHALL create the prorated first-period collection as described under agreement collections.

#### Scenario: Group added on approval

- **WHEN** an agreement whose kind grants group G is approved
- **THEN** the organization is a member of group G

#### Scenario: Permanent code with kind accesses

- **WHEN** an agreement whose kind lists accesses A and B is approved
- **THEN** a permanent code with accesses exactly A and B exists for the organization
- **AND** the permanent code created email is sent

#### Scenario: Kind without accesses

- **WHEN** an agreement whose kind lists no accesses is approved
- **THEN** no permanent code is created

#### Scenario: Deposit collection created

- **WHEN** an agreement whose kind requires a deposit is approved with a deposit amount
- **THEN** a deposit collection with that amount and the agreement's start date as due date exists

### Requirement: Ending an agreement

The system SHALL allow a manager to end an active agreement on a given date, defaulting to today. A future end date SHALL NOT be before the agreement's start date; ending immediately SHALL be possible before the start date, for an agreement withdrawn before it began. The given date SHALL replace an existing end date. With today or a past date the agreement SHALL end immediately. With a future date the system SHALL only save the end date and remove the agreement's collections for periods starting after it: planned ones are deleted and notified ones cancelled; the agreement SHALL stay active with its group, code and remaining collections until a daily command ends it after that date. Changing the end date in the manager's edit form SHALL remove collections in the same way. Ending SHALL set the status `Ended`, SHALL remove the kind's group unless another active agreement of the organization grants the same group, SHALL set the validity end of the agreement's permanent code to the end date when it has one, SHALL remove collections for periods starting after the end date as above, SHALL create a deposit refund record when a paid deposit exists, and SHALL send an ended email. A daily command SHALL end active agreements whose end date has passed. The agreement page SHALL show a scheduled end date while the agreement is still active.

#### Scenario: Manager ends an agreement

- **WHEN** a manager ends an active agreement with no end date whose kind grants a permanent code, without entering a date
- **THEN** the status becomes `Ended` with today as end date
- **AND** the organization is no longer in the kind's group
- **AND** the agreement's permanent code has a validity end
- **AND** planned collections for later periods are removed

#### Scenario: Ending scheduled for a future date

- **WHEN** a manager ends an active membership agreement with the end date 31 December of the current year
- **THEN** the agreement stays `Active` with that end date and the organization stays in the member group
- **AND** no ended email is sent
- **AND** the agreement page shows the scheduled end date

#### Scenario: Scheduled end reached

- **WHEN** the daily command runs on the day after a scheduled end date
- **THEN** the agreement is ended with that end date, the group is removed and the ended email is sent

#### Scenario: Collections after a scheduled end

- **WHEN** an end date is scheduled for an agreement that has a planned and a notified collection for periods starting after it
- **THEN** the planned collection is deleted and the notified collection is cancelled

#### Scenario: Scheduled end moved later

- **WHEN** a manager moves a scheduled end date later
- **THEN** the new date is saved and the daily job creates the planned collections up to it again

#### Scenario: Date replaces an existing end date

- **WHEN** a manager ends an agreement that has a fixed end date next year with today's date
- **THEN** the agreement ends today

#### Scenario: Future date before the start

- **WHEN** a manager enters a future end date before the agreement's start date
- **THEN** the action is refused with a message

#### Scenario: Withdrawn before the start

- **WHEN** a manager ends an active agreement today whose start date is next month
- **THEN** the agreement ends today and all its planned collections are removed

#### Scenario: Ending an agreement without code

- **WHEN** a manager ends an active membership agreement, whose kind grants no permanent code
- **THEN** the agreement is ended and no permanent code is touched

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

The system SHALL show an organization's agreements with status, amount and collections to its confirmed users. Managers SHALL see a list of agreements filterable by kind and status within their scope, with a count of submitted agreements, and the organization list SHALL link to it. Other users SHALL be denied.

#### Scenario: Organization user sees own agreements

- **WHEN** a confirmed user of an organization opens the organization's agreements page
- **THEN** all agreements of that organization are listed

#### Scenario: Foreign user denied

- **WHEN** a user without a confirmed permission on the organization opens its agreements page
- **THEN** the action is denied

#### Scenario: Manager list filtered by status

- **WHEN** a manager filters the agreement list by `Submitted`
- **THEN** only submitted agreements of kinds within the manager's scope are listed

### Requirement: Existing agreements entered in the admin

Staff SHALL be able to create an active agreement with its mandate in the admin for an organization that already holds the kind's group, without triggering the approval side effects. Managers SHALL be able to do the same in the frontend as described in `manager-agreement-management`.

#### Scenario: Existing member entered

- **WHEN** staff create an active membership agreement with a paper mandate reference for an organization that is already in the member group
- **THEN** the agreement and mandate exist, no email is sent, and the organization's groups and codes are unchanged

