## ADDED Requirements

### Requirement: Manager can create an additional permanent code for an organization

The system SHALL allow a manager to create a permanent access code for an organization at `/organizations/manage-organizations/` regardless of whether the organization already has one or more active permanent codes. Creating a code MUST NOT invalidate or modify any existing code; the new code is created as an additional, independently valid code.

#### Scenario: Create the first permanent code

- **WHEN** a manager triggers the create action for an organization that has no active permanent code
- **THEN** the system creates a new permanent code for the organization
- **AND** the manager organization list reflects the new code

#### Scenario: Create an additional code when an active code already exists

- **WHEN** a manager triggers the create action for an organization that already has one or more active permanent codes
- **THEN** the system creates a new permanent code without raising a validation error
- **AND** the existing active codes remain valid and unchanged

#### Scenario: Create action is available in the UI when active codes exist

- **WHEN** a manager views an organization that has one or more active permanent codes
- **THEN** the "Create Code" action is available
- **AND** the create dialog warns that the organization already has an active code before proceeding

#### Scenario: Manager names the new code

- **WHEN** a manager provides a name while creating a permanent code
- **THEN** the new code is created with that name

#### Scenario: Manager leaves the name blank

- **WHEN** a manager creates a permanent code without providing a name (or with only whitespace)
- **THEN** the new code is created with a default name derived from the organization name

### Requirement: Permanent code management is restricted to managers

The system SHALL restrict creating, adding additional, invalidating, and renewing organization permanent codes to authenticated managers. Requests from users without a manager role MUST be denied.

#### Scenario: Non-manager is denied

- **WHEN** a user without a manager role attempts a permanent code action
- **THEN** the system denies the request with a forbidden response

#### Scenario: Anonymous user is redirected

- **WHEN** an anonymous user attempts a permanent code action
- **THEN** the system redirects the user to the login page
