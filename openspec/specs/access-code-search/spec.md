# access-code-search Specification

## Purpose
TBD - created by archiving change add-access-code-search. Update Purpose after archive.
## Requirements
### Requirement: Manager can find bookings by access code

The system SHALL provide an access-code search field at `/bookings/manage-bookings/` that returns the bookings which display the searched code, whether that code originates from the booking's own `access_code` or from a permanent code.

#### Scenario: Search by a booking's own access code

- **WHEN** a manager searches for the access code of a confirmed booking on a resource whose access has a smartlock, and whose organization has no permanent code for that access
- **THEN** the booking is returned

#### Scenario: Search by an organization permanent code

- **WHEN** a manager searches for a permanent code belonging to an organization
- **THEN** every booking of that organization on a resource covered by the code's accesses, whose start falls within the code's validity, is returned

#### Scenario: Search by a general permanent code

- **WHEN** a manager searches for a permanent code with no organization
- **THEN** the bookings that display that code are returned
- **AND** bookings whose organization has its own permanent code for the same access are not returned

#### Scenario: Search is scoped to the manager

- **WHEN** a manager searches for a code that matches a booking outside their organizations or resources
- **THEN** that booking is not returned

### Requirement: Access code search never returns bookings that do not display the code

Because `Booking.access_code` is populated by a default generator for every booking, a stored code is not necessarily the code shown to anyone. The system SHALL confirm each candidate with the booking's derived access code and exclude any booking whose displayed code differs from the search term.

#### Scenario: Stored code is shadowed by an organization permanent code

- **WHEN** a booking's stored `access_code` equals the search term, but the booking's organization has a valid permanent code for the resource's access
- **THEN** the booking is not returned, because the permanent code is what the booking displays

#### Scenario: Stored code on a resource without a smartlock

- **WHEN** a booking's stored `access_code` equals the search term, but the resource's access has no smartlock
- **THEN** the booking is not returned

#### Scenario: Booking has no access at all

- **WHEN** a booking's stored `access_code` equals the search term, but the resource has no access
- **THEN** the booking is not returned

### Requirement: Blank access code input performs no search

The system SHALL treat an empty or whitespace-only access-code input, and input shorter than three characters, as no search at all rather than as a filter on an empty code.

#### Scenario: Empty input

- **WHEN** a manager submits the booking list with an empty access-code field
- **THEN** the list is filtered exactly as it would be without the field
- **AND** bookings whose stored `access_code` is empty are not selected by that field

#### Scenario: Whitespace-only input

- **WHEN** a manager submits an access-code value consisting only of whitespace
- **THEN** no access-code filtering is applied

#### Scenario: Surrounding whitespace is ignored

- **WHEN** a manager submits an access code with leading or trailing whitespace
- **THEN** the trimmed value is used for matching

### Requirement: An access code search relaxes the booking list defaults

The booking list defaults to pending bookings and hides past and recurring bookings. Since a caller's booking is typically confirmed and may already have started, the system SHALL NOT apply the status, past-bookings or recurring-bookings filters while an access-code search is active, and SHALL make that visible by disabling those controls for the duration of the search. Date ranges are exempt: the filter form always submits a value for the status select and omits unchecked boxes, so an explicit choice cannot be distinguished from the form default, whereas an unset date input submits an empty value and remains distinguishable.

#### Scenario: Confirmed booking is found without changing the status filter

- **WHEN** a manager searches for the code of a confirmed booking while the status filter is at its default
- **THEN** the booking is returned

#### Scenario: Booking that has already started is found

- **WHEN** a manager searches for the code of a booking that started earlier and has already ended, while the past-bookings option is at its default
- **THEN** the booking is returned

#### Scenario: Explicit date range still applies

- **WHEN** a manager searches for a code and has set a from-date or until-date
- **THEN** only matching bookings within that range are returned

#### Scenario: Relaxed filters are shown as disabled

- **WHEN** an access-code search is active
- **THEN** the status, past-bookings and recurring-bookings controls are disabled
- **AND** the results state that those filters are not being applied

### Requirement: Access code results are bounded by a default date window

A single permanent code can cover thousands of bookings. The system SHALL restrict access-code results to a default window around the current date when the manager has set no explicit date range, SHALL state the applied window in the results, and SHALL offer a way to see all dates.

#### Scenario: Default window is applied and disclosed

- **WHEN** a manager searches for a permanent code without setting a date range
- **THEN** only bookings within the default window are returned
- **AND** the results state which window was applied

#### Scenario: Manager removes the window

- **WHEN** a manager chooses to show all dates
- **THEN** every booking displaying that code within their scope is returned

#### Scenario: Explicit date range wins

- **WHEN** a manager searches for a code and has set a from-date or until-date
- **THEN** the manager's range is used and the default window is not applied

#### Scenario: Results are ordered by proximity to now

- **WHEN** an access-code search returns more than one booking
- **THEN** bookings closest to the current time are listed first

### Requirement: Matched bookings show the code they display

The system SHALL show each matched booking's displayed access code in the results while an access-code search is active, and SHALL NOT render that column otherwise.

#### Scenario: Code column during a search

- **WHEN** an access-code search is active
- **THEN** each returned booking shows its displayed access code

#### Scenario: No code column without a search

- **WHEN** no access-code search is active
- **THEN** the access code column is not rendered

### Requirement: Organization search matches permanent codes

The system SHALL match the search field at `/organizations/manage-organizations/` against organization permanent codes as well as organization names, including codes that have expired, so that a caller holding a no-longer-valid code can still be identified.

#### Scenario: Search by an active permanent code

- **WHEN** a manager searches the organization list for an active permanent code
- **THEN** the organization holding that code is returned

#### Scenario: Search by an expired permanent code

- **WHEN** a manager searches the organization list for an expired permanent code
- **THEN** the organization that held the code is returned

#### Scenario: Organization with several codes appears once

- **WHEN** a search matches an organization holding more than one permanent code
- **THEN** the organization appears exactly once in the results

#### Scenario: Name search is unaffected

- **WHEN** a manager searches the organization list by name
- **THEN** matching organizations are returned as before

### Requirement: Access code search is restricted to managers

The system SHALL restrict access-code search to authenticated managers, and SHALL return only bookings belonging to the manager's organizations and resources.

#### Scenario: Non-manager is denied

- **WHEN** a user without a manager role requests the booking list with an access-code search
- **THEN** the system denies the request with a forbidden response

#### Scenario: Anonymous user is redirected

- **WHEN** an anonymous user requests the booking list with an access-code search
- **THEN** the system redirects the user to the login page

