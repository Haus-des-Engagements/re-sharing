## MODIFIED Requirements

### Requirement: Agreement visibility

The system SHALL show an organization's agreements with status, amount and collections to its confirmed users. Managers SHALL see a list of agreements filterable by kind, status and whether the agreement has an open mandate, within their scope, with a count of submitted agreements, and the organization list SHALL link to it. The list SHALL show for each agreement the reference of its open mandate, the one that is not revoked, linked to the mandate and marked while its signed document is missing. Other users SHALL be denied.

#### Scenario: Organization user sees own agreements

- **WHEN** a confirmed user of an organization opens the organization's agreements page
- **THEN** all agreements of that organization are listed

#### Scenario: Foreign user denied

- **WHEN** a user without a confirmed permission on the organization opens its agreements page
- **THEN** the action is denied

#### Scenario: Manager list filtered by status

- **WHEN** a manager filters the agreement list by `Submitted`
- **THEN** only submitted agreements of kinds within the manager's scope are listed

#### Scenario: Manager list shows the mandate reference

- **WHEN** a manager opens the agreement list and an agreement has a mandate that is not revoked
- **THEN** the agreement's row shows the mandate's reference, linked to the mandate

#### Scenario: Mandate awaiting the signed document

- **WHEN** an agreement's open mandate has no signed document
- **THEN** the reference is shown with a note that the signed mandate is awaited

#### Scenario: Manager list filtered by mandate

- **WHEN** a manager filters the agreement list by `without SEPA mandate`
- **THEN** only agreements without a mandate or with revoked mandates only are listed
