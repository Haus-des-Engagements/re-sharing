# organization-custom-email Specification

## Purpose
TBD - created by archiving change custom-email-date-range-resource-filters. Update Purpose after archive.
## Requirements
### Requirement: Custom email page is manager-only

The custom organization email page and its send endpoint SHALL be accessible only to managers.

#### Scenario: Non-manager is denied
- **WHEN** a logged-in non-manager user requests the custom email page
- **THEN** the request is rejected as it is for other manager-only pages

### Requirement: Only confirmed organizations are candidates

The filtered organization list SHALL contain only organizations with status `Confirmed`.

#### Scenario: Pending organization is excluded
- **WHEN** a manager previews organizations with no filters other than an organization group that contains a `Pending` and a `Confirmed` organization
- **THEN** only the `Confirmed` organization is listed

### Requirement: Booking statistics count confirmed bookings starting within the date range

For every candidate organization the system SHALL compute `booking_count` and `total_amount` over bookings that have status `Confirmed` and whose start lies within the selected date range. `from_date` and `to_date` are calendar days interpreted in the project time zone. The range is inclusive: it starts at `from_date` 00:00:00 and ends at `to_date` 23:59:59.999999. Either bound MAY be omitted; an omitted bound is open. When neither bound is given, all confirmed bookings count. Dates in the future SHALL be accepted.

#### Scenario: Booking starting at the beginning of from_date counts
- **WHEN** `from_date` is 2026-03-01 and a confirmed booking starts on 2026-03-01 at 00:00 local time
- **THEN** the booking is included in `booking_count` and `total_amount`

#### Scenario: Booking starting late on to_date counts
- **WHEN** `to_date` is 2026-03-31 and a confirmed booking starts on 2026-03-31 at 23:30 local time
- **THEN** the booking is included in `booking_count` and `total_amount`

#### Scenario: Booking starting the day after to_date does not count
- **WHEN** `to_date` is 2026-03-31 and a confirmed booking starts on 2026-04-01 at 00:00 local time
- **THEN** the booking is not included

#### Scenario: Booking starting the day before from_date does not count
- **WHEN** `from_date` is 2026-03-01 and a confirmed booking starts on 2026-02-28 at 23:59 local time
- **THEN** the booking is not included

#### Scenario: Booking that starts before the range but ends inside it does not count
- **WHEN** `from_date` is 2026-03-01 and a confirmed booking runs from 2026-02-28 22:00 to 2026-03-01 02:00
- **THEN** the booking is not included

#### Scenario: Only from_date given
- **WHEN** `from_date` is 2026-03-01 and `to_date` is empty
- **THEN** every confirmed booking starting on or after 2026-03-01 00:00 counts, with no upper limit

#### Scenario: Only to_date given
- **WHEN** `to_date` is 2026-03-31 and `from_date` is empty
- **THEN** every confirmed booking starting on or before 2026-03-31 23:59:59 counts, with no lower limit

#### Scenario: No dates given yields all-time statistics
- **WHEN** neither `from_date` nor `to_date` is given
- **THEN** all confirmed bookings of the organization count regardless of date

#### Scenario: Future range counts future confirmed bookings
- **WHEN** `from_date` and `to_date` both lie after today and a confirmed booking starts within that range
- **THEN** the booking is included

#### Scenario: Non-confirmed bookings never count
- **WHEN** an organization has a `Pending` or `Cancelled` booking starting within the range
- **THEN** it is excluded from `booking_count` and `total_amount`

### Requirement: Date range must be valid

The system SHALL reject a filter where `from_date` is later than `to_date` or where a date cannot be parsed, show an error message to the manager and SHALL NOT list or email any organization for that request.

#### Scenario: from_date after to_date on preview
- **WHEN** a manager previews with `from_date` 2026-04-01 and `to_date` 2026-03-01
- **THEN** an error message is shown and no organizations are listed

#### Scenario: Invalid date on send
- **WHEN** the send request carries a `from_date` that is not a valid date
- **THEN** no email is enqueued and the manager is redirected back with an error message

### Requirement: Resource filter narrows counted bookings to rooms and parking lots

The manager SHALL be able to select multiple resources. Only resources of type `room` or `parking_lot` SHALL be offered, grouped by type. When resources are selected, only confirmed bookings on those resources count towards `booking_count` and `total_amount`. When no resource is selected, bookings on all resources count. Resource IDs of any other type SHALL be ignored server-side.

#### Scenario: Resource options exclude lendable items
- **WHEN** the manager opens the page and resources of type `room`, `parking_lot` and `lendable_item` exist
- **THEN** the resource select lists the room and the parking lot and does not list the lendable item

#### Scenario: Selected resource narrows the count
- **WHEN** an organization has two confirmed bookings on room A and one on room B and the manager selects room A
- **THEN** `booking_count` is 2 and `total_amount` is the sum of the two room A bookings

#### Scenario: Multiple selected resources are combined
- **WHEN** the manager selects room A and parking lot P and the organization has confirmed bookings on A, P and room B
- **THEN** bookings on A and P count and the booking on B does not

#### Scenario: No selection counts all resources
- **WHEN** no resource is selected
- **THEN** bookings on every resource count

#### Scenario: Lendable item ID is ignored
- **WHEN** a request contains the ID of a `lendable_item` resource in the resource filter and no other resource
- **THEN** the ID is dropped and no bookings count for any organization

#### Scenario: Resource filter combines with date range
- **WHEN** room A is selected and `from_date`/`to_date` are set
- **THEN** only confirmed bookings on room A starting within the range count

### Requirement: Booking count and amount thresholds apply regardless of date range

The manager SHALL be able to set `min_bookings` (organizations with fewer counted bookings are excluded) and `max_amount` (organizations whose counted total amount exceeds it are excluded). Both SHALL apply whether or not a date range or resource filter is set. A `min_bookings` of `0` SHALL be treated as a set value.

#### Scenario: min_bookings without date range
- **WHEN** `min_bookings` is 2 and no dates are given and organization X has 1 all-time confirmed booking while organization Y has 3
- **THEN** only Y is listed

#### Scenario: max_amount without date range
- **WHEN** `max_amount` is 100 and no dates are given and organization X has all-time confirmed total of 150 while Y has 50
- **THEN** only Y is listed

#### Scenario: Thresholds use narrowed statistics
- **WHEN** room A is selected, `min_bookings` is 2 and an organization has 3 confirmed bookings in total but only 1 on room A
- **THEN** the organization is not listed

### Requirement: Organization group include and exclude filters

The manager SHALL be able to restrict candidates to organizations in any of the included groups and to remove organizations in any of the excluded groups. Empty selections mean no restriction.

#### Scenario: Include and exclude combined
- **WHEN** group G1 is included and group G2 is excluded and organization X is in both
- **THEN** X is not listed

### Requirement: Preview shows per-organization statistics and carries filters to the send form

The preview list SHALL show each organization's name, email, `booking_count` and `total_amount` for the current filter, and the send form SHALL carry the identical filter parameters (`include_groups`, `exclude_groups`, `from_date`, `to_date`, `resources`, `min_bookings`, `max_amount`) as hidden fields.

#### Scenario: Hidden fields mirror the filter
- **WHEN** a manager previews with `from_date`, `to_date` and two resources selected
- **THEN** the send form contains hidden inputs for those values and the organization table shows the narrowed counts

### Requirement: Sending emails only to previewed and selected organizations

On send, the system SHALL re-apply the submitted filters, keep only the organizations the manager checked, and enqueue one email task per remaining organization with the filter context.

#### Scenario: Unchecked organization receives no email
- **WHEN** the filter matches X and Y and the manager checks only X
- **THEN** exactly one task is enqueued, for X

#### Scenario: Selected organization no longer matching is skipped
- **WHEN** the manager checks X but X does not match the submitted filters at send time
- **THEN** no task is enqueued for X

### Requirement: Email template context reflects the filter statistics

Each sent email SHALL be rendered with `organization`, `domain`, `number_of_bookings`, `total_amount`, `from_date`, `to_date`, `min_bookings` and `max_amount` available. `number_of_bookings` and `total_amount` SHALL be computed with the same rules as the preview (confirmed bookings, start within range, selected resources). `from_date` and `to_date` SHALL be rendered as localized short dates (e.g. `01.03.2026`) or as an empty string when the bound is open. `months` SHALL NOT be available.

#### Scenario: total_amount is populated
- **WHEN** an organization has confirmed bookings with amounts 10 and 20 in the range and the body template contains `{{ total_amount }}`
- **THEN** the sent email body contains `30`

#### Scenario: number_of_bookings respects resource filter
- **WHEN** the filter context selects room A and the organization has 2 confirmed bookings on A and 1 on B in the range
- **THEN** `{{ number_of_bookings }}` renders `2`

#### Scenario: Dates are formatted
- **WHEN** the filter context has `from_date` 2026-03-01 and `to_date` 2026-03-31 and the body contains `{{ from_date }} - {{ to_date }}`
- **THEN** the email body contains `01.03.2026 - 31.03.2026`

#### Scenario: Open bound renders empty
- **WHEN** the filter context has no `to_date` and the body contains `[{{ to_date }}]`
- **THEN** the email body contains `[]`

#### Scenario: All-time statistics when no dates
- **WHEN** the filter context has neither date and the organization has 5 confirmed bookings in total
- **THEN** `{{ number_of_bookings }}` renders `5`

### Requirement: Page help lists the available template tags

The page SHALL document the available email template tags: `organization.name`, `organization.email`, `number_of_bookings`, `total_amount`, `from_date`, `to_date`, and SHALL NOT mention `months`.

#### Scenario: Help text after preview
- **WHEN** a manager previews organizations
- **THEN** the compose section lists `from_date` and `to_date` as template tags and does not list `months`

