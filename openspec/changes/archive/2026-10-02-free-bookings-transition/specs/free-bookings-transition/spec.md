## ADDED Requirements

### Requirement: Transition selects the legacy bookings of limited organizations

The transition SHALL consider only organizations with status confirmed whose effective allowance is limited. For such an organization it SHALL select bookings that are pending or confirmed, have `uses_free_booking` false, an empty invoice number, a compensation that counts against free bookings, a start in the future and a limited allowance on their start date. Standalone bookings and occurrences of series with `is_quota_priced` false SHALL both be selected; unavailable occurrences SHALL NOT.

#### Scenario: Legacy single booking and series occurrence are selected

- **WHEN** a limited organization has a future 2027 booking and a future 2027 occurrence of a legacy series, both with the consuming compensation and `uses_free_booking` false
- **THEN** both are part of the transition

#### Scenario: Unlimited organization is skipped

- **WHEN** an organization is in a limited group and in a group without a number
- **THEN** none of its bookings are touched

#### Scenario: Past, invoiced and unflagged bookings are skipped

- **WHEN** a limited organization has a booking that already started, a booking with an invoice number, a booking with a paid compensation and a booking before the limit's valid-from date
- **THEN** none of them is touched

### Requirement: Free bookings are allocated chronologically per year

For each calendar year the transition SHALL sort the selected bookings by start and set `uses_free_booking` true on the first ones until the organization's remaining free bookings of that year, computed before the run, are used.

#### Scenario: Earliest bookings stay free

- **WHEN** a limited organization with an allowance of 5 and 2 quota-priced free bookings in 2027 has 6 legacy 2027 bookings
- **THEN** the 3 earliest legacy bookings get `uses_free_booking` true and the other 3 do not

#### Scenario: Allowance applies per year

- **WHEN** the same organization also has 4 legacy 2028 bookings and no quota-priced 2028 bookings
- **THEN** all 4 get `uses_free_booking` true

### Requirement: Bookings beyond the allowance are charged with the cheapest paid compensation

A selected booking that gets no free booking SHALL be priced with the cheapest active hourly compensation bookable by the organization for its resource, for its full duration, with `uses_free_booking` false.

#### Scenario: Charged at the cheapest rate

- **WHEN** a 2 hour legacy booking gets no free booking and the room has paid compensations at 15 and 20 €/h bookable by the organization
- **THEN** the booking gets the 15 €/h compensation and a total amount of 30 €

### Requirement: Bookings without a paid compensation are removed

Where no paid compensation is bookable for the resource, a selected series occurrence beyond the allowance SHALL be deleted and a selected standalone booking beyond the allowance SHALL be cancelled. No email SHALL be sent by the transition.

#### Scenario: Series occurrence deleted

- **WHEN** a legacy occurrence beyond the allowance is on a room without a paid compensation
- **THEN** the occurrence is deleted

#### Scenario: Standalone booking cancelled

- **WHEN** a legacy standalone booking beyond the allowance is on a room without a paid compensation
- **THEN** its status becomes cancelled and no email is enqueued

### Requirement: Legacy series are marked as quota-priced

Every series of a limited organization with `is_quota_priced` false and a compensation that counts against free bookings SHALL get `is_quota_priced` true and, where one exists, the cheapest paid compensation of its resource as `fallback_compensation`, whether or not it currently has selectable occurrences. Series with another compensation SHALL NOT be changed.

#### Scenario: Series gets fallback and marker

- **WHEN** a limited organization has a legacy weekly series with the consuming compensation on a room with a 15 €/h compensation
- **THEN** the series has `is_quota_priced` true and the 15 €/h compensation as fallback

#### Scenario: Series on a room without paid compensation

- **WHEN** the room has no paid compensation
- **THEN** the series has `is_quota_priced` true and no fallback

#### Scenario: Paid series untouched

- **WHEN** a legacy series uses a compensation with an hourly rate
- **THEN** its `is_quota_priced` stays false

### Requirement: Dry run performs no change

With `--dry-run` the command SHALL compute and print the same report as a real run and SHALL leave every booking and series unchanged.

#### Scenario: Dry run

- **WHEN** the command runs with `--dry-run` for an organization with legacy bookings
- **THEN** the report lists the free, charged and removed bookings
- **AND** no booking, series or status in the database differs from before

### Requirement: Report per organization

The command SHALL print, for every processed organization, the allowance and remaining free bookings per year before the run, the numbers of bookings kept free, charged (with the total amount), deleted and cancelled, and the series updated. At verbosity 2 it SHALL list every booking with date, resource and outcome. Organizations without selected bookings and without legacy series SHALL be reported as nothing to do.

#### Scenario: Summary output

- **WHEN** the command processes an organization with 3 free, 2 charged and 1 deleted booking
- **THEN** the output contains the organization's name with those counts and the charged total

### Requirement: The command is idempotent and can be restricted

A second run after a completed run SHALL change nothing. `--organizations` with organization slugs SHALL restrict the run to those organizations; an unknown slug SHALL fail the command before any change.

#### Scenario: Second run

- **WHEN** the command runs twice
- **THEN** the second run reports nothing to do for every organization

#### Scenario: Restricted run

- **WHEN** the command runs with `--organizations org-a`
- **THEN** only the bookings and series of `org-a` are changed

### Requirement: One organization is processed under its lock

The transition of one organization SHALL run in its own transaction with the organization row locked, so that a failure in one organization does not roll back the others and concurrent bookings of the organization are serialized with it.

#### Scenario: Failure in one organization

- **WHEN** processing one organization raises an error
- **THEN** the changes of the organizations processed before are kept and the error is reported
