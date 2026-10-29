## MODIFIED Requirements

### Requirement: SEPA collection runs

The system SHALL allow a manager to build a run for a chosen collection date from all notified collections whose agreement has an active mandate at that time and whose due date is up to that date. Each collection in the run SHALL use the agreement's mandate active when the run is built, regardless of the mandate present when the collection was created. The run SHALL produce a pain.008 CORE XML file in private storage with batch booking disabled, sequence type RCUR, the collection reference as end-to-end id, the mandate reference and signature date, and the creditor data from settings. Collections in the run SHALL become `Submitted`. A manager SHALL mark a run as uploaded. A run not marked uploaded SHALL be deletable, returning its collections to `Notified`; an uploaded run SHALL NOT be deletable.

#### Scenario: Build a run

- **WHEN** a manager builds a run for 2027-03-05 and three notified collections are due by then
- **THEN** a run with three transactions and the summed amount exists and its XML file can be downloaded
- **AND** the XML carries each collection's reference as end-to-end id and each mandate's reference
- **AND** the three collections are `Submitted` and reference the run

#### Scenario: Deposit in the run

- **WHEN** a notified deposit collection is due by the collection date
- **THEN** it is included in the run under the agreement's mandate

#### Scenario: Collection without mandate excluded

- **WHEN** the agreement of a notified collection has no active mandate
- **THEN** it is not included in a run and is listed as needing attention

#### Scenario: Mandate added after the collection

- **WHEN** a collection was created while its agreement had no mandate and a signed mandate is added before the run
- **THEN** the run includes the collection with that mandate and it no longer needs attention

#### Scenario: New mandate after revocation

- **WHEN** the mandate of a notified collection is revoked and a new signed mandate is added
- **THEN** the run includes the collection with the new mandate's reference

#### Scenario: Mark uploaded

- **WHEN** a manager marks a run as uploaded
- **THEN** the run stores the upload time and the manager

#### Scenario: Delete a run before upload

- **WHEN** a manager deletes a run that is not marked uploaded
- **THEN** its collections are `Notified` again and no longer reference the run

#### Scenario: Delete an uploaded run

- **WHEN** a manager tries to delete an uploaded run
- **THEN** the action is refused

### Requirement: Pre-notification

When a planned collection reaches its notification date (due date minus the configured pre-notification days), the system SHALL assign the agreement's active mandate to it when there is one, SHALL send a pre-notification email naming amount, due date, mandate reference and creditor identifier when the kind's notification mode is per collection, and SHALL send nothing when the mode is once at approval. In both cases the collection SHALL become `Notified`. The approval email of a kind with mode once at approval SHALL state amount, interval and collection date. First-year collections of yearly kinds are notified at creation and SHALL NOT receive a pre-notification email.

#### Scenario: Per-collection notification

- **WHEN** the notification date of a collection of a kind with per-collection mode is reached
- **THEN** the organization receives the pre-notification email
- **AND** the collection status is `Notified`

#### Scenario: Mandate added after the collection was planned

- **WHEN** a collection was planned without mandate and the agreement has an active mandate at the notification date
- **THEN** the pre-notification names that mandate's reference

#### Scenario: Once-at-approval mode

- **WHEN** the notification date of a collection of a kind with once-at-approval mode is reached
- **THEN** no email is sent
- **AND** the collection status is `Notified`

#### Scenario: Approval email as standing notification

- **WHEN** an agreement of a kind with once-at-approval mode is approved
- **THEN** the decision email states amount, billing interval and collection date
