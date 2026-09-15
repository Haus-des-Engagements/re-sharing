## ADDED Requirements

### Requirement: Organization group free-bookings allowance

An organization group SHALL have an optional `free_bookings_per_year` (positive integer) and an optional `free_bookings_valid_from` (date). A group with no `free_bookings_per_year` grants an unlimited allowance. A group with a value but with `free_bookings_valid_from` after the date in question grants an unlimited allowance for that date. Both fields SHALL be editable in the admin.

#### Scenario: Group without a value is unlimited

- **WHEN** an organization group has no `free_bookings_per_year`
- **THEN** its allowance for any date is unlimited

#### Scenario: Group value not yet valid is unlimited

- **WHEN** an organization group has `free_bookings_per_year` 5 and `free_bookings_valid_from` 2027-01-01
- **THEN** its allowance for 2026-12-31 is unlimited
- **AND** its allowance for 2027-01-01 is 5 bookings

### Requirement: Effective allowance of an organization

The effective allowance of an organization for a given date SHALL be the most generous allowance across all of its organization groups, where unlimited is more generous than any number.

#### Scenario: Member in the default group stays unlimited

- **WHEN** an organization is in a group with `free_bookings_per_year` 5 and in a group with no value
- **THEN** its effective allowance is unlimited

#### Scenario: Highest number wins among limited groups

- **WHEN** an organization is in a group with 5 bookings and in a group with 12 bookings, both valid
- **THEN** its effective allowance is 12 bookings

#### Scenario: Organization only in limited groups

- **WHEN** an organization is only in groups with `free_bookings_per_year` 5
- **THEN** its effective allowance is 5 bookings

### Requirement: Compensation consumes free bookings only when flagged

A compensation SHALL have a boolean `counts_against_free_bookings`, default false, editable in the admin. Only bookings priced with a flagged compensation use free bookings.

#### Scenario: Rate-less compensation without flag does not consume

- **WHEN** a booking is created with a compensation that has no hourly rate and `counts_against_free_bookings` false
- **THEN** the booking's `uses_free_booking` is false

### Requirement: Free bookings used per calendar year

Each booking SHALL store `uses_free_booking` (boolean, default false). A booking SHALL count as exactly one free booking regardless of its duration. The free bookings used by an organization in a calendar year SHALL be the number of the organization's bookings with `uses_free_booking` true whose `start_date` lies in that year and whose status is `Pending` or `Confirmed`. The remaining free bookings SHALL be the effective allowance minus the used free bookings, never below zero, and unlimited when the allowance is unlimited.

#### Scenario: Pending and confirmed bookings count

- **WHEN** an organization with an allowance of 5 has a pending free booking and a confirmed free booking in 2027
- **THEN** its free bookings used in 2027 are 2 and its remaining free bookings are 3

#### Scenario: Duration does not matter

- **WHEN** an organization has a free 1 hour booking and a free 8 hour booking in 2027
- **THEN** its free bookings used in 2027 are 2

#### Scenario: Cancelled booking returns its free booking

- **WHEN** a free booking of 2027 is cancelled
- **THEN** it is no longer counted for 2027

#### Scenario: Bookings of other years do not count

- **WHEN** an organization has free bookings in 2026 and 2027
- **THEN** only bookings with `start_date` in 2027 count towards the 2027 usage

#### Scenario: Excluding a booking from the count

- **WHEN** the usage is computed while excluding a given booking
- **THEN** that booking is not counted

#### Scenario: Existing bookings do not count

- **WHEN** the allowance is configured after bookings with the free compensation already exist for 2027
- **THEN** those bookings have `uses_free_booking` false and do not count towards the 2027 usage
