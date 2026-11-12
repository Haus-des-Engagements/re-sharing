## MODIFIED Requirements

### Requirement: Transition selects the legacy bookings of limited organizations

The transition SHALL consider only organizations with status confirmed whose effective allowance is limited. For such an organization it SHALL select bookings that are pending or confirmed, have `uses_free_booking` false, an empty invoice number, a compensation that counts against free bookings, a resource that is not exempt from free bookings, a start in the future and a limited allowance on their start date. Standalone bookings and occurrences of series with `is_quota_priced` false SHALL both be selected; unavailable occurrences SHALL NOT.

#### Scenario: Legacy single booking and series occurrence are selected

- **WHEN** a limited organization has a future 2027 booking and a future 2027 occurrence of a legacy series, both with the consuming compensation and `uses_free_booking` false
- **THEN** both are part of the transition

#### Scenario: Unlimited organization is skipped

- **WHEN** an organization is in a limited group and in a group without a number
- **THEN** none of its bookings are touched

#### Scenario: Past, invoiced and unflagged bookings are skipped

- **WHEN** a limited organization has a booking that already started, a booking with an invoice number, a booking with a paid compensation and a booking before the limit's valid-from date
- **THEN** none of them is touched

#### Scenario: Bookings on an exempt resource are skipped

- **WHEN** a limited organization with an allowance of 2 has 3 future legacy bookings on an exempt resource followed by 3 on a resource that is not exempt, all with the consuming compensation
- **THEN** the 3 bookings on the exempt resource are not touched
- **AND** the first 2 bookings on the other resource are kept free and the third is beyond the allowance

### Requirement: Legacy series are marked as quota-priced

Every series of a limited organization with `is_quota_priced` false, a compensation that counts against free bookings and a resource that is not exempt from free bookings SHALL get `is_quota_priced` true and, where one exists, the cheapest paid compensation of its resource as `fallback_compensation`, whether or not it currently has selectable occurrences. Series with another compensation or on an exempt resource SHALL NOT be changed.

#### Scenario: Series gets fallback and marker

- **WHEN** a limited organization has a legacy weekly series with the consuming compensation on a room with a 15 €/h compensation
- **THEN** the series has `is_quota_priced` true and the 15 €/h compensation as fallback

#### Scenario: Series on a room without paid compensation

- **WHEN** the room has no paid compensation
- **THEN** the series has `is_quota_priced` true and no fallback

#### Scenario: Paid series untouched

- **WHEN** a legacy series uses a compensation with an hourly rate
- **THEN** its `is_quota_priced` stays false

#### Scenario: Series on an exempt resource untouched

- **WHEN** a legacy series uses the consuming compensation on an exempt resource
- **THEN** its `is_quota_priced` stays false and it has no fallback
