## ADDED Requirements

### Requirement: Two-factor authentication for staff and managers

The system SHALL require users with staff status, superusers and managers to have two-factor authentication set up. Until they have, the system SHALL redirect every request of theirs to the two-factor setup, except account pages, logout, static and media files and ending an impersonation. Other users SHALL NOT be required to set up two-factor authentication. Enforcement SHALL be switchable by the setting `REQUIRE_STAFF_MFA`, on by default.

#### Scenario: Manager without two-factor authentication

- **WHEN** a manager without authenticator opens the manager agreement list
- **THEN** they are redirected to the two-factor setup with a message

#### Scenario: Staff in the admin

- **WHEN** a staff user without authenticator opens the admin
- **THEN** they are redirected to the two-factor setup

#### Scenario: Setup reachable

- **WHEN** a manager without authenticator opens the two-factor setup or logs out
- **THEN** the page is shown without redirect

#### Scenario: Manager with two-factor authentication

- **WHEN** a manager with an authenticator app set up opens the manager agreement list
- **THEN** the page is shown

#### Scenario: Other users

- **WHEN** an organization admin without authenticator opens their organization's agreements
- **THEN** the page is shown

#### Scenario: Impersonation

- **WHEN** staff impersonate a manager without authenticator
- **THEN** the impersonated session is not redirected

#### Scenario: Enforcement switched off

- **WHEN** `REQUIRE_STAFF_MFA` is off
- **THEN** managers without authenticator are not redirected
