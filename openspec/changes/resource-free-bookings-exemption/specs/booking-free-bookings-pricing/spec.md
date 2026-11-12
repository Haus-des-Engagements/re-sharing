## ADDED Requirements

### Requirement: Bookings on exempt resources are not priced against the allowance

On a resource that is exempt from free bookings, a compensation that counts against free bookings SHALL be treated like one that does not, in every step that prices or checks a booking: the booking is free, `uses_free_booking` is false, and neither preview nor save fails because the allowance is used up. This applies to single bookings and to every occurrence of a series.

#### Scenario: Booking with exhausted allowance

- **WHEN** an organization with no free booking left in 2027 books an exempt resource in 2027 with the flagged compensation
- **THEN** the booking is saved with no total amount and `uses_free_booking` false

#### Scenario: Series occurrences on an exempt resource

- **WHEN** an organization with an allowance of 5 creates a weekly series with the flagged compensation on an exempt resource
- **THEN** every occurrence keeps the flagged compensation with `uses_free_booking` false
- **AND** no occurrence is charged with a fallback or dropped

#### Scenario: Booking on another resource is still limited

- **WHEN** the same organization with no free booking left books a resource that is not exempt with the flagged compensation and no paid compensation exists
- **THEN** the booking is rejected because no free booking is left

### Requirement: Booking form on exempt resources ignores the allowance

For a resource that is exempt from free bookings, the compensation choices SHALL include compensations that count against free bookings even when no free booking of the year is left, SHALL show no remaining free bookings hint, and a series SHALL NOT be asked for a fallback compensation.

#### Scenario: Flagged compensation stays offered

- **WHEN** an organization with no free booking left opens the booking form for an exempt resource
- **THEN** the flagged compensation is offered
- **AND** no remaining free bookings hint is shown

#### Scenario: Series without fallback

- **WHEN** a limited organization opens the series form for an exempt resource that also has a paid compensation
- **THEN** no fallback compensation is requested
- **AND** the series can be saved without one
