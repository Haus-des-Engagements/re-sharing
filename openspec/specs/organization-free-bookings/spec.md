# organization-free-bookings Specification

## Purpose

Yearly free bookings allowance per organization group with a valid-from date, the effective allowance of an organization (most generous group wins, unlimited beats any number), the compensation flag that consumes free bookings, and the counting of used free bookings per calendar year. Changes to the allowance affect only later bookings; users see their used free bookings per organization on the dashboard.

## Requirements

### Requirement: Organization group free-bookings allowance

An organization group SHALL have an optional `free_bookings_per_year` (positive integer) and an optional `free_bookings_valid_from` (date). The two fields SHALL be set together: a group with a number but no date, or a date but no number, SHALL be rejected on validation and by a database constraint. A group with no `free_bookings_per_year` grants an unlimited allowance. A group with a value but with `free_bookings_valid_from` after the date in question grants an unlimited allowance for that date. Both fields SHALL be editable in the admin.

#### Scenario: Number without a date is rejected

- **WHEN** an organization group is saved with `free_bookings_per_year` 5 and no `free_bookings_valid_from`
- **THEN** validation fails on `free_bookings_valid_from` and the group is not saved

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

### Requirement: Changes to the allowance affect only later bookings

Changing `free_bookings_per_year`, `free_bookings_valid_from` or `counts_against_free_bookings` SHALL NOT change `compensation`, `total_amount` or `uses_free_booking` of any existing booking. The remaining free bookings SHALL be computed from the current allowance and the stored flags, never below zero.

#### Scenario: Allowance lowered after bookings exist

- **WHEN** an organization has 5 free bookings with `uses_free_booking` true in 2027 and its group's `free_bookings_per_year` is changed from 5 to 3
- **THEN** the five bookings keep their compensation, amount and flag
- **AND** the organization's remaining free bookings in 2027 are 0

#### Scenario: Organization loses its unlimited group

- **WHEN** an organization that was unlimited has 10 free bookings with `uses_free_booking` false in 2027 and is removed from its unlimited group, leaving it with an allowance of 5
- **THEN** the ten bookings stay free and unflagged
- **AND** the organization's remaining free bookings in 2027 are 5

### Requirement: Compensation consumes free bookings only when flagged

A compensation SHALL have a boolean `counts_against_free_bookings`, default false, editable in the admin. Only bookings priced with a flagged compensation use free bookings. A compensation with an `hourly_rate` or a `daily_rate` SHALL NOT be flagged; validation and a database constraint SHALL reject it.

#### Scenario: Priced compensation cannot be flagged

- **WHEN** a compensation with an hourly rate of 15 is saved with `counts_against_free_bookings` true
- **THEN** validation fails on `counts_against_free_bookings` and the compensation is not saved

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

#### Scenario: Free booking keeps an empty amount

- **WHEN** a booking of a limited organization is priced with the consuming compensation and a free booking is left
- **THEN** its `total_amount` is empty, as for any compensation without a rate

#### Scenario: Existing bookings do not count

- **WHEN** the allowance is configured after bookings with the free compensation already exist for 2027
- **THEN** those bookings have `uses_free_booking` false and do not count towards the 2027 usage

### Requirement: Used free bookings on the user dashboard

The user dashboard SHALL show, for each of the user's organizations with a limited allowance, the used and available free bookings of the current calendar year and of the following year. Organizations with an unlimited allowance SHALL show nothing.

#### Scenario: Limited organization on the dashboard

- **WHEN** a user whose organization has an allowance of 5, 3 used free bookings in the current year and 5 used free bookings in the following year opens the dashboard
- **THEN** the organization's row shows 3 of 5 for the current year and 5 of 5 for the following year

#### Scenario: Unlimited organization on the dashboard

- **WHEN** a user whose organization has an unlimited allowance opens the dashboard
- **THEN** the organization's row shows no free-bookings information

#### Scenario: Allowance not yet valid in the current year

- **WHEN** the allowance is valid from 2027-01-01, the current year is 2026 and the user opens the dashboard
- **THEN** the organization's row shows no information for 2026 and the used free bookings of 2027
