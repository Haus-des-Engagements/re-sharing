# booking-free-bookings-pricing Specification

## Purpose

How single bookings, booking edits and booking series occurrences are priced against the organization's remaining free bookings: which compensations are offered, the paid fallback for series, the server-side guard and locking, how pre-quota bookings and series are left untouched, and what the user is told in the selector and the previews.

## Requirements

### Requirement: Pricing a booking against the free-bookings allowance

When a booking is priced with a compensation that counts against free bookings and the organization's effective allowance for the booking's start date is limited, the system SHALL apply the following rules using the remaining free bookings of the calendar year of the booking's start date:

- If at least one free booking remains, the booking keeps the consuming compensation, `total_amount` stays empty (`None`, as for any compensation without a rate), and `uses_free_booking` is true.
- If no free booking remains and a fallback compensation is given (booking series only), the booking is priced with the fallback compensation for its full duration, and `uses_free_booking` is false.
- If no free booking remains and no fallback is given, the booking cannot be priced with the consuming compensation.

There SHALL be no partial coverage: a booking is either fully free or fully paid. When the allowance is unlimited or the compensation does not count, pricing SHALL be unchanged from today.

#### Scenario: Free booking left

- **WHEN** an organization has 3 remaining free bookings in 2027 and books a 3 hour slot with the consuming compensation
- **THEN** the booking is free, with `uses_free_booking` true and `total_amount` empty
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

#### Scenario: Booking before the valid-from date is not limited

- **WHEN** the organization's only group has `free_bookings_per_year` 5 and `free_bookings_valid_from` 2027-01-01, and a booking starting 2026-12-31 is created with the consuming compensation, at any creation date
- **THEN** the booking is free, `uses_free_booking` is false, and no fallback or remaining count applies

#### Scenario: Booking on the valid-from date is limited

- **WHEN** the same organization creates a booking starting 2027-01-01 with the consuming compensation, even while the current date is in 2026
- **THEN** the booking uses one of the 2027 free bookings

### Requirement: Compensation choices reflect the allowance

The compensation selector SHALL not offer a consuming compensation when the organization has no remaining free bookings in the year of the selected start date and its allowance is limited. When it is offered to an organization with a limited allowance, the selector SHALL show the remaining free bookings for that year. The server-side bookability check SHALL enforce the same rule regardless of what the form submitted, for managers as for everyone else.

When a booking is edited, the selector SHALL keep the booking's current compensation in the choices as long as the organization and the calendar year of the start date in the request equal those of the booking, and SHALL exclude the booking itself from the remaining free bookings it shows.

When a booking series is requested and a paid fallback compensation is available for the resource and the organization, the selector SHALL offer the consuming compensation and the bookability check SHALL accept it even when no free booking remains in the year of the first occurrence. When no paid fallback is available, the rule SHALL apply to the first occurrence of the series.

#### Scenario: Consuming compensation hidden when exhausted

- **WHEN** the compensation selector is requested for a limited organization with 0 remaining free bookings in the selected year
- **THEN** the consuming compensation is not in the rendered choices

#### Scenario: Remaining free bookings shown

- **WHEN** the compensation selector is requested for a limited organization with 2 remaining free bookings
- **THEN** the consuming compensation is listed with a note showing 2 remaining free bookings for that year

#### Scenario: Submitting a hidden compensation is rejected

- **WHEN** a limited organization with 0 remaining free bookings submits a booking with the consuming compensation id
- **THEN** the bookability check fails and no booking is created

#### Scenario: Manager booking for a limited organization

- **WHEN** a manager submits a booking for a limited organization with 0 remaining free bookings with the consuming compensation
- **THEN** the bookability check fails and no booking is created

#### Scenario: Room without paid compensation becomes unbookable

- **WHEN** a limited organization with 0 remaining free bookings requests choices for a room whose only bookable compensation is the consuming one
- **THEN** the rendered choices are empty and the booking cannot be submitted

#### Scenario: Editing a booking created before the quota keeps its compensation in the choices

- **WHEN** the selector is requested for the edit of a 2027 booking with the consuming compensation and `uses_free_booking` false, with the same organization and a start date in 2027, and the organization has 0 remaining free bookings in 2027
- **THEN** the consuming compensation is in the rendered choices and selected

#### Scenario: Editing a free booking does not count the booking itself

- **WHEN** the selector is requested for the edit of a free 2027 booking of an organization with an allowance of 5 and 5 used free bookings in 2027, with the same organization and a start date in 2027
- **THEN** the consuming compensation is in the rendered choices with a note showing 1 remaining free booking

#### Scenario: Edit moved to an exhausted year hides the compensation

- **WHEN** the selector is requested for the edit of a free 2027 booking with a start date in 2028 and the organization has 0 remaining free bookings in 2028
- **THEN** the consuming compensation is not in the rendered choices

#### Scenario: Series starting in an exhausted year with a fallback

- **WHEN** a limited organization with 0 remaining free bookings in 2027 and its full allowance in 2028 requests the choices for a series starting in 2027 on a room with a paid compensation
- **THEN** the consuming compensation is in the rendered choices
- **AND** the series can be saved with the consuming compensation and a fallback, its 2027 occurrences are priced with the fallback and its first 2028 occurrences are free

#### Scenario: Series starting in an exhausted year without a fallback

- **WHEN** the same organization requests the choices for a series starting in 2027 on a room without a paid compensation
- **THEN** the consuming compensation is not in the rendered choices and submitting it is rejected

### Requirement: Booking preview shows the pricing outcome

The single booking preview SHALL state, for a booking of a limited organization with the consuming compensation, that it uses a free booking and how many free bookings remain in that year afterwards.

#### Scenario: Preview of a free booking

- **WHEN** a user of a limited organization with 3 remaining free bookings previews a booking with the consuming compensation
- **THEN** the preview states that the booking uses one free booking and that 2 remain for that year

### Requirement: Exhausted allowance at preview or save is reported

When the single booking preview or its save finds that no free booking remains for the consuming compensation, the system SHALL NOT create or change the booking, SHALL tell the user that no free booking is left for that year and that another compensation has to be chosen, and SHALL return the user to the booking form with the entered data.

#### Scenario: Last free booking taken after the form was submitted

- **WHEN** a user submits a booking with the consuming compensation while 1 free booking remains, and another booking of the organization uses it before the preview is saved
- **THEN** saving creates no booking and the user is returned to the booking form with a message that no free booking is left

### Requirement: Editing a booking re-checks it only when relevant

When an existing booking is edited and the organization, the compensation or the calendar year of the start date changes, the system SHALL re-price it with the pricing rules, excluding the booking itself from the used free bookings, against the year of the new start date. When none of these change, the system SHALL keep the booking's `uses_free_booking` value, SHALL NOT apply the quota rule in the bookability check, and SHALL compute `total_amount` as today from the compensation's hourly rate and the booking's duration.

#### Scenario: Edit within the same year stays free

- **WHEN** a free booking of an organization with 0 other remaining free bookings is edited from 2 to 4 hours and moved to another room within the same year
- **THEN** the booking stays free with `uses_free_booking` true

#### Scenario: Editing a booking created before the quota

- **WHEN** a 2027 booking with the consuming compensation and `uses_free_booking` false, created before the allowance was configured, gets a new title and the organization has 0 remaining free bookings in 2027
- **THEN** the edit is accepted, the booking stays free and `uses_free_booking` stays false

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

#### Scenario: Series crossing the valid-from date

- **WHEN** an organization whose only group has `free_bookings_per_year` 5 valid from 2027-01-01 creates a weekly series from 2026-11-02 into 2027 with the consuming compensation and a fallback
- **THEN** all 2026 occurrences are free with `uses_free_booking` false
- **AND** the first five 2027 occurrences are free with `uses_free_booking` true and later 2027 occurrences are priced with the fallback

#### Scenario: Fallback priced at the current rate

- **WHEN** the fallback of a quota-priced series had a rate of 15 €/h at creation and has 20 €/h when the nightly extension creates a 2 hour occurrence beyond the allowance
- **THEN** that occurrence is priced at 40 € and earlier occurrences keep their stored amounts

#### Scenario: Fallback no longer usable

- **WHEN** the fallback of a quota-priced series is inactive when the nightly extension creates an occurrence beyond the allowance
- **THEN** the occurrence is not created

#### Scenario: Nightly extension respects the allowance

- **WHEN** the extension command creates an occurrence for a quota-priced series with the consuming compensation and the organization has no remaining free bookings in that occurrence's year
- **THEN** the occurrence is priced with the series fallback compensation

#### Scenario: Occurrence that cannot be priced is not created

- **WHEN** an occurrence of a quota-priced series can neither be covered by a remaining free booking nor priced with a fallback
- **THEN** it is not created, at series creation and in the nightly extension alike

### Requirement: Series created before the quota keep today's pricing

A booking series SHALL have a boolean `is_quota_priced`, default false. Series created through the booking series creation flow after this change SHALL set it to true. Every path that generates occurrences (series creation, the nightly extension and the "Generate bookings" admin action) SHALL price occurrences with the pricing rules only for series with `is_quota_priced` true; for other series it SHALL keep today's behaviour, using the series compensation and `total_amount_per_booking`, with `uses_free_booking` false.

#### Scenario: Existing series is not cut off by the quota

- **WHEN** a series created before this change uses the consuming compensation, has no fallback, and the organization has 0 remaining free bookings in the year of the next occurrence
- **THEN** the extension creates the occurrence with the series compensation and `uses_free_booking` false

#### Scenario: Admin action on an existing series

- **WHEN** the "Generate bookings" admin action runs for a series with `is_quota_priced` false that uses the consuming compensation, and the organization has 0 remaining free bookings
- **THEN** the occurrences are created with the series compensation and `total_amount_per_booking` and `uses_free_booking` false

#### Scenario: Admin action on a quota-priced series

- **WHEN** the "Generate bookings" admin action runs for a series with `is_quota_priced` true and the organization has 0 remaining free bookings in the year of a new occurrence
- **THEN** that occurrence is priced with the series fallback compensation

#### Scenario: New series is marked as quota-priced

- **WHEN** a series is created through the series creation flow
- **THEN** its `is_quota_priced` is true

### Requirement: Series form requires a fallback when needed

When the selected compensation counts against free bookings, the organization's allowance is limited on any occurrence date between the first occurrence and the end of the booking horizon (today plus 730 days, or the series' last date if earlier), and at least one active compensation with an hourly rate is bookable by the organization for the resource, the series form SHALL require the user to select one of those as `fallback_compensation`.

#### Scenario: Fallback required

- **WHEN** a limited organization submits a series with the consuming compensation on a room with a paid compensation and no fallback selected
- **THEN** the form is invalid with an error on the fallback field

#### Scenario: Fallback required for a series starting before the valid-from date

- **WHEN** an organization whose allowance is limited from 2027-01-01 submits, in 2026, a weekly series starting 2026-11-02 without an end date with the consuming compensation on a room with a paid compensation and no fallback selected
- **THEN** the form is invalid with an error on the fallback field

#### Scenario: Fallback not required for a series ending before the valid-from date

- **WHEN** the same organization submits a series that ends on 2026-12-20
- **THEN** no fallback is required

#### Scenario: Fallback not required for unlimited organizations

- **WHEN** an organization with an unlimited allowance submits a series with the consuming compensation
- **THEN** no fallback is required

### Requirement: Saving a series is checked and serialized

Saving a booking series SHALL apply the server-side bookability check to the series compensation. It SHALL reject a fallback compensation that is inactive, has no hourly rate or is not bookable by the organization for the resource, and SHALL reject a series without a fallback when the series form would require one. Saving SHALL lock the organization and price the occurrences again before they are stored, so that the stored prices reflect the free bookings remaining at the time of saving. The nightly extension and the admin action SHALL price and save each series in its own transaction under the same lock.

#### Scenario: Series with a compensation that is not bookable

- **WHEN** a series is saved with a compensation that is not bookable by the organization
- **THEN** saving is rejected and neither the series nor any occurrence is created

#### Scenario: Series with an invalid fallback

- **WHEN** a series is saved with a fallback compensation that is inactive or not bookable by the organization for the resource
- **THEN** saving is rejected and neither the series nor any occurrence is created

#### Scenario: Free bookings used between preview and save

- **WHEN** the preview of a series showed 5 free occurrences in 2027 and the organization uses 2 free bookings in 2027 before the series is saved
- **THEN** the saved series has 3 free occurrences in 2027 and the other 2027 occurrences are priced with the fallback

#### Scenario: Failure in one series does not affect the others

- **WHEN** the nightly extension fails while processing one series
- **THEN** the occurrences created for the other series are kept

### Requirement: Unavailable occurrences are priced when they become confirmed

When the confirmation of a booking series with `is_quota_priced` true changes an occurrence from `Unavailable` to `Confirmed`, the system SHALL price that occurrence with the pricing rules and the series fallback against the allowance of its own year before confirming it. An occurrence that cannot be priced SHALL be deleted. Series with `is_quota_priced` false SHALL keep today's behaviour.

#### Scenario: Occurrence becomes available and uses a free booking

- **WHEN** a quota-priced series is confirmed, one of its unavailable 2027 occurrences no longer overlaps a confirmed booking, and the organization has 1 remaining free booking in 2027
- **THEN** the occurrence is confirmed with `uses_free_booking` true and the organization has 0 remaining free bookings in 2027

#### Scenario: Occurrence becomes available after the allowance is used

- **WHEN** the same happens and the organization has 0 remaining free bookings in 2027 and the series has a fallback
- **THEN** the occurrence is confirmed and priced with the fallback compensation for its full duration

#### Scenario: Occurrence becomes available but cannot be priced

- **WHEN** the same happens and the organization has 0 remaining free bookings in 2027 and the series has no fallback
- **THEN** the occurrence is deleted

### Requirement: Admin edits of a series keep per-occurrence pricing

Saving a booking series with `is_quota_priced` true in the admin SHALL NOT change `compensation`, `total_amount` or `uses_free_booking` of its bookings. Series with `is_quota_priced` false SHALL keep today's behaviour.

#### Scenario: Title change of a quota-priced series

- **WHEN** the title of a quota-priced series with 5 free and 10 fallback-priced occurrences is changed in the admin
- **THEN** all occurrences get the new title
- **AND** each occurrence keeps its compensation, amount and `uses_free_booking`

#### Scenario: Title change of a series created before the quota

- **WHEN** the title of a series with `is_quota_priced` false is changed in the admin
- **THEN** its occurrences get the series compensation and `total_amount_per_booking`, as today

### Requirement: Series preview shows the pricing breakdown

The series preview SHALL show how many occurrences are free, how many are paid and at which rate, the resulting total, and how many occurrences were dropped because they could not be priced.

#### Scenario: Preview breakdown

- **WHEN** a user previews a series with 5 free and 47 paid occurrences at 15 €/h
- **THEN** the preview lists those counts, the rate and the total amount

#### Scenario: Preview mentions dropped occurrences

- **WHEN** a series preview contains occurrences that could not be priced
- **THEN** the preview states the number of dropped occurrences and the reason

### Requirement: Existing bookings are not re-priced

Deploying or configuring the allowance SHALL NOT change `compensation`, `total_amount` or `uses_free_booking` of any existing booking. Deploying the change without configuring any allowance or compensation flag SHALL leave pricing of new bookings unchanged.

#### Scenario: Setting an allowance leaves existing bookings untouched

- **WHEN** an allowance is configured on a group after bookings already exist
- **THEN** those bookings keep their stored compensation and amount and do not count as free bookings

#### Scenario: Deploy without configuration

- **WHEN** the change is deployed and no group has `free_bookings_per_year` and no compensation has `counts_against_free_bookings`
- **THEN** new bookings and series are priced exactly as before
