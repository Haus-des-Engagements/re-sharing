# organization-lifecycle Specification

## Purpose
TBD - created by archiving change deactivate-organizations. Update Purpose after archive.
## Requirements
### Requirement: Organization status values

An organization SHALL have exactly one status from the following set: `Pending`, `Confirmed`, `Rejected`, `Deactivated`. `Pending` is the default for a newly created organization. `Rejected` represents a moral block (the organization is not allowed to book). `Deactivated` represents a neutral, reversible inactive state with no implication of wrongdoing.

#### Scenario: New organization defaults to pending

- **WHEN** an organization is created by a non-manager user
- **THEN** its status is `Pending`

#### Scenario: Organization created by a manager is confirmed

- **WHEN** an organization is created by a manager
- **THEN** its status is `Confirmed`

### Requirement: Only confirmed organizations can book

The system SHALL block booking creation for any organization whose status is not `Confirmed`. This applies to `Pending`, `Rejected`, and `Deactivated` organizations.

#### Scenario: Deactivated organization cannot book

- **WHEN** a non-manager user attempts to create a booking for an organization with status `Deactivated`
- **THEN** the booking is not allowed

#### Scenario: Confirmed organization can book

- **WHEN** a non-manager confirmed member attempts to create a booking for an organization with status `Confirmed`
- **THEN** the organization status does not prevent the booking

### Requirement: Manager can deactivate a confirmed organization

A manager SHALL be able to deactivate an organization whose status is `Confirmed`, moving it to `Deactivated`. Deactivation SHALL NOT send any email. Deactivation SHALL NOT be permitted from any status other than `Confirmed`.

#### Scenario: Deactivate a confirmed organization

- **WHEN** a manager deactivates an organization with status `Confirmed`
- **THEN** the organization status becomes `Deactivated`
- **AND** no email is sent

#### Scenario: Deactivation not offered for non-confirmed organizations

- **WHEN** an organization has status `Pending`, `Rejected`, or `Deactivated`
- **THEN** the deactivate action is not available for it

#### Scenario: Deactivation by a non-manager is rejected

- **WHEN** a non-manager user attempts to deactivate an organization
- **THEN** the action is denied

### Requirement: Manager can activate a deactivated organization

A manager SHALL be able to activate an organization whose status is `Deactivated`, moving it back to `Confirmed` so that it can book again. Activation SHALL NOT send any email. Activation SHALL NOT be permitted from any status other than `Deactivated`.

#### Scenario: Activate a deactivated organization

- **WHEN** a manager activates an organization with status `Deactivated`
- **THEN** the organization status becomes `Confirmed`
- **AND** no email is sent

#### Scenario: Activation not offered for non-deactivated organizations

- **WHEN** an organization has status `Pending`, `Confirmed`, or `Rejected`
- **THEN** the activate action is not available for it

#### Scenario: Activation by a non-manager is rejected

- **WHEN** a non-manager user attempts to activate an organization
- **THEN** the action is denied

### Requirement: Rejected state remains a separate moral block

The `Rejected` status SHALL remain distinct from `Deactivated`. The activate action SHALL NOT transition a `Rejected` organization to `Confirmed`; re-enabling a rejected organization is out of scope for the activate transition.

#### Scenario: Activate does not apply to rejected organizations

- **WHEN** an organization has status `Rejected`
- **THEN** activating it is not available and its status is unchanged
