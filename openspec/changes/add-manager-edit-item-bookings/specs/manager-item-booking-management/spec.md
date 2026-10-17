## ADDED Requirements

### Requirement: Manager can add an item to a booking group

The system SHALL provide a manager-only action that adds a new item (a `Booking`) to an existing equipment booking group. The action MUST reuse the group's existing pickup and return dates and MUST NOT apply availability or lending-day validation (manager override). The manager MUST supply a resource and quantity, and MAY supply a custom price.

#### Scenario: Add an item with a custom price

- **WHEN** a manager submits the add-item action for a booking group with a resource, quantity, and a custom total amount
- **THEN** a new item booking is created in that group with the given resource, quantity, and total amount
- **AND** the group's total amount reflects the added item

#### Scenario: Add an item to a past booking group

- **WHEN** a manager adds an item to a booking group whose pickup and return dates are in the past
- **THEN** the item is added successfully without availability or lending-day validation errors

#### Scenario: Non-manager is denied

- **WHEN** a user who is not a manager attempts the add-item action
- **THEN** access is denied and no item is created

### Requirement: Item bookings never use free bookings

Item bookings SHALL never use one of the organization's free bookings. When a compensation is chosen for an item booking — by the customer item flow or the manager add-item action — compensations that count against free bookings SHALL NOT be chosen. Item bookings SHALL always have `uses_free_booking` false and SHALL NOT reduce the organization's remaining free bookings.

#### Scenario: Customer item booking skips a free-booking compensation

- **WHEN** a customer books an item whose resource has a compensation that counts against free bookings and a paid compensation
- **THEN** the item booking uses the paid compensation
- **AND** `uses_free_booking` is false

#### Scenario: Manager add-item skips a free-booking compensation

- **WHEN** a manager adds an item whose resource has a compensation that counts against free bookings and a paid compensation
- **THEN** the new item booking uses the paid compensation
- **AND** `uses_free_booking` is false

#### Scenario: Only free-booking compensations available

- **WHEN** an item's resource only has compensations that count against free bookings
- **THEN** the item booking is rejected with a "no compensation available" error

#### Scenario: Item bookings do not reduce remaining free bookings

- **WHEN** an organization with a limited allowance books items
- **THEN** its remaining free bookings for that year are unchanged

### Requirement: Manager can set a custom price on an item

The system SHALL allow a manager to set a custom price on an individual item in a booking group by editing that item's total amount directly.

#### Scenario: Update item total amount

- **WHEN** a manager submits a new total amount for an item in a booking group
- **THEN** that item's total amount is updated to the submitted value
- **AND** the group's total amount reflects the updated item

### Requirement: Manager can cancel items and booking groups including past bookings

The system SHALL allow a manager to cancel a whole booking group or a single item within it, regardless of whether the booking is in the past. Cancelling an item SHALL set its status to Cancelled while retaining the record. The manager detail view SHALL present the cancel actions whenever the group or item is not already cancelled, including for past bookings.

#### Scenario: Cancel a past booking group

- **WHEN** a manager cancels a booking group whose dates are in the past and which is not already cancelled
- **THEN** the group and its items are set to Cancelled

#### Scenario: Cancel actions shown for past bookings

- **WHEN** a manager opens the detail page of a past booking group that is not cancelled
- **THEN** the "Cancel All" action and per-item cancel actions are displayed

#### Scenario: Remove item keeps the record

- **WHEN** a manager removes (cancels) a single item in a booking group
- **THEN** the item's status is set to Cancelled
- **AND** the item remains visible in the booking group

### Requirement: Manager can post a customer-visible comment without email

The system SHALL allow a manager to post a comment on a booking group, stored as a `BookingMessage`. Posting the comment MUST NOT send or enqueue any email notification. The comment SHALL be visible both to the manager and to the customer on their booking-group page.

#### Scenario: Post a comment without sending email

- **WHEN** a manager posts a comment on a booking group
- **THEN** a booking message is created for that group
- **AND** no booking-message email is sent or enqueued

#### Scenario: Customer can see the comment

- **WHEN** the customer opens their booking-group page after a manager posted a comment
- **THEN** the comment is displayed to the customer
