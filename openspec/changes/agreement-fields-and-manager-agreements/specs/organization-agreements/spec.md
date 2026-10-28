## MODIFIED Requirements

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

### Requirement: Existing agreements entered in the admin

Staff SHALL be able to create an active agreement with its mandate in the admin for an organization that already holds the kind's group, without triggering the approval side effects. Managers SHALL be able to do the same in the frontend as described in `manager-agreement-management`.

#### Scenario: Existing member entered

- **WHEN** staff create an active membership agreement with a paper mandate reference for an organization that is already in the member group
- **THEN** the agreement and mandate exist, no email is sent, and the organization's groups and codes are unchanged
