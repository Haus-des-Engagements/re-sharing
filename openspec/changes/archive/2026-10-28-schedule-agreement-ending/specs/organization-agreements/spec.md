## MODIFIED Requirements

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
