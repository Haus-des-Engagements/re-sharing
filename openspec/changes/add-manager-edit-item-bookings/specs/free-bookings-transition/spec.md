## MODIFIED Requirements

### Requirement: Transition selects the legacy bookings of limited organizations

The transition SHALL consider only organizations with status confirmed whose effective allowance is limited. For such an organization it SHALL select bookings that are pending or confirmed, have `uses_free_booking` false, an empty invoice number, a compensation that counts against free bookings, a start in the future and a limited allowance on their start date. Standalone bookings and occurrences of series with `is_quota_priced` false SHALL both be selected; unavailable occurrences SHALL NOT. Item bookings SHALL NOT be selected, since they never use free bookings.

#### Scenario: Legacy single booking and series occurrence are selected

- **WHEN** a limited organization has a future 2027 booking and a future 2027 occurrence of a legacy series, both with the consuming compensation and `uses_free_booking` false
- **THEN** both are part of the transition

#### Scenario: Unlimited organization is skipped

- **WHEN** an organization is in a limited group and in a group without a number
- **THEN** none of its bookings are touched

#### Scenario: Past, invoiced and unflagged bookings are skipped

- **WHEN** a limited organization has a booking that already started, a booking with an invoice number, a booking with a paid compensation and a booking before the limit's valid-from date
- **THEN** none of them is touched


#### Scenario: Item bookings are skipped

- **WHEN** a limited organization has a future item booking whose compensation counts against free bookings
- **THEN** it is not touched
