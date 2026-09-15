## ADDED Requirements

### Requirement: Pricing a booking against the free-bookings allowance

When a booking is priced with a compensation that counts against free bookings and the organization's effective allowance for the booking's start date is limited, the system SHALL apply the following rules using the remaining free bookings of the calendar year of the booking's start date:

- If at least one free booking remains, the booking keeps the consuming compensation, `total_amount` is 0, and `uses_free_booking` is true.
- If no free booking remains and a fallback compensation is given (booking series only), the booking is priced with the fallback compensation for its full duration, and `uses_free_booking` is false.
- If no free booking remains and no fallback is given, the booking cannot be priced with the consuming compensation.

There SHALL be no partial coverage: a booking is either fully free or fully paid. When the allowance is unlimited or the compensation does not count, pricing SHALL be unchanged from today.

#### Scenario: Free booking left

- **WHEN** an organization has 3 remaining free bookings in 2027 and books a 3 hour slot with the consuming compensation
- **THEN** the booking is free, with `uses_free_booking` true and `total_amount` 0
- **AND** the organization has 2 remaining free bookings in 2027

#### Scenario: Long booking uses one free booking

- **WHEN** an organization has 1 remaining free booking in 2027 and books an 8 hour slot with the consuming compensation
- **THEN** the booking is free and the organization has 0 remaining free bookings in 2027

#### Scenario: No remaining free bookings

- **WHEN** an organization has 0 remaining free bookings in 2027 and selects the consuming compensation for a single 2027 booking
- **THEN** the booking is rejected as not bookable

#### Scenario: Unlimited organization unaffected

- **WHEN** an organization with an unlimited allowance books with the consuming compensation
- **THEN** the booking is free and `uses_free_booking` is false

#### Scenario: Quota year follows the start date

- **WHEN** an organization has exhausted 2026 but not 2027 and books a slot starting 2027-01-03 with the consuming compensation
- **THEN** the booking is priced against the 2027 remaining free bookings

### Requirement: Compensation choices reflect the allowance

The compensation selector SHALL not offer a consuming compensation when the organization has no remaining free bookings in the year of the selected start date and its allowance is limited. When it is offered to an organization with a limited allowance, the selector SHALL show the remaining free bookings for that year. The server-side bookability check SHALL enforce the same rule regardless of what the form submitted.

#### Scenario: Consuming compensation hidden when exhausted

- **WHEN** the compensation selector is requested for a limited organization with 0 remaining free bookings in the selected year
- **THEN** the consuming compensation is not in the rendered choices

#### Scenario: Remaining free bookings shown

- **WHEN** the compensation selector is requested for a limited organization with 2 remaining free bookings
- **THEN** the consuming compensation is listed with a note showing 2 remaining free bookings for that year

#### Scenario: Submitting a hidden compensation is rejected

- **WHEN** a limited organization with 0 remaining free bookings submits a booking with the consuming compensation id
- **THEN** the bookability check fails and no booking is created

#### Scenario: Room without paid compensation becomes unbookable

- **WHEN** a limited organization with 0 remaining free bookings requests choices for a room whose only bookable compensation is the consuming one
- **THEN** the rendered choices are empty and the booking cannot be submitted

### Requirement: Booking preview shows the pricing outcome

The single booking preview SHALL state, for a booking of a limited organization with the consuming compensation, that it uses a free booking and how many free bookings remain in that year afterwards.

#### Scenario: Preview of a free booking

- **WHEN** a user of a limited organization with 3 remaining free bookings previews a booking with the consuming compensation
- **THEN** the preview states that the booking uses one free booking and that 2 remain for that year

### Requirement: Editing a booking re-checks it

When an existing booking is edited, the system SHALL re-price it with the same rules, excluding the booking itself from the used free bookings, against the year of the new start date.

#### Scenario: Edit within the same year stays free

- **WHEN** a free booking of an organization with 0 other remaining free bookings is edited from 2 to 4 hours within the same year
- **THEN** the booking stays free with `uses_free_booking` true

#### Scenario: Edit into an exhausted year

- **WHEN** a free 2027 booking is moved to a date in 2028 for which the organization has 0 remaining free bookings
- **THEN** the edit is rejected

#### Scenario: Paid booking switched to the consuming compensation

- **WHEN** a paid booking is edited to use the consuming compensation and the organization has 1 remaining free booking in that year
- **THEN** the booking becomes free with `uses_free_booking` true and the organization has 0 remaining free bookings

### Requirement: Booking series occurrences are priced individually

Each occurrence of a booking series SHALL count as one booking and SHALL be priced with the pricing rules against the allowance of the occurrence's own year, both when the series is created and when the nightly extension creates new occurrences. Occurrences generated in one run SHALL count earlier free occurrences of the same run as used. Occurrences with status `Unavailable` SHALL NOT use a free booking. A booking series SHALL store an optional `fallback_compensation` that is used as the paid compensation for occurrences the allowance does not cover.

#### Scenario: Series exceeds the yearly allowance

- **WHEN** a limited organization with 5 remaining free bookings in 2027 creates a weekly 2 hour series through 2027 with the consuming compensation and a 15 €/h fallback
- **THEN** the first five occurrences in 2027 are free, and all later 2027 occurrences are priced at 30 € with the fallback compensation

#### Scenario: Unavailable occurrence does not use a free booking

- **WHEN** the second occurrence of such a series is unavailable because the room is already booked
- **THEN** the free bookings go to the first, third, fourth, fifth and sixth occurrence

#### Scenario: Allowance resets in the next year

- **WHEN** the same series continues into 2028 and the organization has its full allowance for 2028
- **THEN** the 2028 occurrences start free again until the 2028 allowance is used

#### Scenario: Nightly extension respects the allowance

- **WHEN** the extension command creates an occurrence for a series with the consuming compensation and the organization has no remaining free bookings in that occurrence's year
- **THEN** the occurrence is priced with the series fallback compensation

#### Scenario: Occurrence that cannot be priced is not created

- **WHEN** an occurrence can neither be covered by a remaining free booking nor priced with a fallback
- **THEN** it is not created, at series creation and in the nightly extension alike

### Requirement: Series form requires a fallback when needed

When the selected compensation counts against free bookings, the organization's allowance for the first occurrence is limited, and at least one active compensation with an hourly rate is bookable by the organization for the resource, the series form SHALL require the user to select one of those as `fallback_compensation`.

#### Scenario: Fallback required

- **WHEN** a limited organization submits a series with the consuming compensation on a room with a paid compensation and no fallback selected
- **THEN** the form is invalid with an error on the fallback field

#### Scenario: Fallback not required for unlimited organizations

- **WHEN** an organization with an unlimited allowance submits a series with the consuming compensation
- **THEN** no fallback is required

### Requirement: Series preview shows the pricing breakdown

The series preview SHALL show how many occurrences are free, how many are paid and at which rate, the resulting total, and how many occurrences were dropped because they could not be priced.

#### Scenario: Preview breakdown

- **WHEN** a user previews a series with 5 free and 47 paid occurrences at 15 €/h
- **THEN** the preview lists those counts, the rate and the total amount

#### Scenario: Preview mentions dropped occurrences

- **WHEN** a series preview contains occurrences that could not be priced
- **THEN** the preview states the number of dropped occurrences and the reason

### Requirement: Existing bookings are not re-priced

Deploying or configuring the allowance SHALL NOT change `compensation`, `total_amount` or `uses_free_booking` of any existing booking.

#### Scenario: Setting an allowance leaves existing bookings untouched

- **WHEN** an allowance is configured on a group after bookings already exist
- **THEN** those bookings keep their stored compensation and amount and do not count as free bookings
