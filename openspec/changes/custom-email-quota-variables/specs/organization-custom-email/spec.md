## ADDED Requirements

### Requirement: Template tags for bookings above the free bookings allowance

Each custom email SHALL be able to use the template tags `bookings_above_limit`, `cost_above_limit` and `bookings_above_limit_without_rate`. Their values SHALL be the outcome of a dry run of the free bookings transition for the receiving organization, reduced to the bookings that start within the selected date range and, when resources are selected, on those resources:

- `bookings_above_limit` is the number of bookings the transition would charge.
- `cost_above_limit` is the sum of the amounts the transition would charge for them, with two decimals.
- `bookings_above_limit_without_rate` is the number of bookings the transition would remove because the room has no paid compensation.

The free bookings of a calendar year SHALL be allocated across all of the organization's bookings of that year, regardless of the selected date range and resources. The date range SHALL follow the same rules as the booking statistics (inclusive days in the project time zone, open bounds allowed). Rendering an email SHALL NOT change any booking or series.

#### Scenario: Bookings above the allowance are counted with their cost
- **WHEN** an organization with an allowance of 2 has 5 future bookings in 2027 made before the quota, each one hour on a room whose cheapest paid compensation is 10 per hour, and the email covers all of 2027
- **THEN** `bookings_above_limit` renders `3` and `cost_above_limit` renders `30.00`

#### Scenario: Earlier bookings of the year use the allowance first
- **WHEN** that organization's bookings are one per month from January to May 2027 and the date range is March 2027
- **THEN** `bookings_above_limit` renders `1`, because January and February keep the two free bookings

#### Scenario: Period before the allowance is used up
- **WHEN** the date range is January 2027 for the same organization
- **THEN** `bookings_above_limit` renders `0` and `cost_above_limit` renders `0.00`

#### Scenario: Resource filter narrows the reported bookings only
- **WHEN** the organization has 2 bookings on room A followed by 2 on room B in 2027, an allowance of 2, and room B is selected
- **THEN** `bookings_above_limit` renders `2`, because the bookings on room A used the allowance

#### Scenario: Room without a paid compensation
- **WHEN** an organization with an allowance of 1 has 3 future bookings made before the quota on a room without a paid compensation
- **THEN** `bookings_above_limit` renders `0`, `cost_above_limit` renders `0.00` and `bookings_above_limit_without_rate` renders `2`

#### Scenario: Unlimited organization
- **WHEN** the organization belongs to a group without a free bookings number
- **THEN** all three tags render `0` (`0.00` for the cost)

#### Scenario: Bookings already priced against the quota do not count
- **WHEN** an organization's bookings above the allowance were already charged when they were created
- **THEN** `bookings_above_limit` renders `0`

#### Scenario: Open date range
- **WHEN** neither `from_date` nor `to_date` is given
- **THEN** the tags cover all future bookings of the organization the transition would handle

#### Scenario: Rendering changes nothing
- **WHEN** an email using `bookings_above_limit` is sent for an organization with bookings above the allowance
- **THEN** compensation, amount, status and free-booking flag of every booking are the same as before, and no series is marked as quota-priced

#### Scenario: Test email shows the same values
- **WHEN** a manager sends a test email whose body contains `{{ bookings_above_limit }}` and `{{ cost_above_limit }}`
- **THEN** the test email contains the values of the organization it is rendered for

### Requirement: Quota values are only computed when used

The system SHALL run the transition dry run for an email only when its subject or body uses one of the three tags.

#### Scenario: Email without the tags
- **WHEN** a custom email whose subject and body contain none of the three tags is sent
- **THEN** no transition dry run is performed for the organization

### Requirement: Page help lists the quota template tags

The page SHALL document `bookings_above_limit`, `cost_above_limit` and `bookings_above_limit_without_rate` among the available template tags and SHALL state that they cover future bookings not yet priced against the free bookings allowance.

#### Scenario: Help text after preview
- **WHEN** a manager previews organizations
- **THEN** the compose section lists the three tags
