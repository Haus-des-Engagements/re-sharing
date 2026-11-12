## ADDED Requirements

### Requirement: Resource can be exempt from free bookings

A resource SHALL have a boolean `exempt_from_free_bookings`, default false, editable in the admin. Bookings on an exempt resource SHALL NOT use free bookings, whatever their compensation. Changing the value SHALL affect only bookings priced afterwards; bookings that already have `uses_free_booking` true SHALL keep it and still count as used.

#### Scenario: New resource is not exempt

- **WHEN** a resource is created without setting the value
- **THEN** its `exempt_from_free_bookings` is false

#### Scenario: Booking on an exempt resource does not consume

- **WHEN** a limited organization books an exempt resource with a compensation that has `counts_against_free_bookings` true
- **THEN** the booking's `uses_free_booking` is false
- **AND** the organization's used free bookings of that year are unchanged

#### Scenario: Earlier free bookings stay counted

- **WHEN** an organization has 2 bookings with `uses_free_booking` true on a resource and the resource is then set exempt
- **THEN** both bookings keep `uses_free_booking` true
- **AND** the organization's used free bookings of that year are still 2

## MODIFIED Requirements

### Requirement: Compensation consumes free bookings only when flagged

A compensation SHALL have a boolean `counts_against_free_bookings`, default false, editable in the admin. Only bookings priced with a flagged compensation on a resource that is not exempt from free bookings use free bookings. A compensation with an `hourly_rate` or a `daily_rate` SHALL NOT be flagged; validation and a database constraint SHALL reject it.

#### Scenario: Priced compensation cannot be flagged

- **WHEN** a compensation with an hourly rate of 15 is saved with `counts_against_free_bookings` true
- **THEN** validation fails on `counts_against_free_bookings` and the compensation is not saved

#### Scenario: Rate-less compensation without flag does not consume

- **WHEN** a booking is created with a compensation that has no hourly rate and `counts_against_free_bookings` false
- **THEN** the booking's `uses_free_booking` is false

#### Scenario: Flagged compensation on a resource that is not exempt consumes

- **WHEN** a limited organization with free bookings left books a resource that is not exempt with a flagged compensation
- **THEN** the booking's `uses_free_booking` is true
