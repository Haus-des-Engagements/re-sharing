## ADDED Requirements

### Requirement: Single-column card layout

The user dashboard SHALL present its sections as full-width cards stacked in one column, with the same layout on every screen size, and SHALL NOT use tables, so that its content is readable without horizontal scrolling on a 360px-wide screen.

#### Scenario: Dashboard without tables

- **WHEN** a logged-in user opens the dashboard
- **THEN** the page contains no table and shows each section as a card

#### Scenario: Phone width

- **WHEN** the dashboard is viewed at a width of 360px
- **THEN** all content of every row, including status badges, is visible without horizontal scrolling

### Requirement: Section order

The dashboard SHALL show the sections in this order: the user's organizations, the upcoming bookings and requests, and — for managers only — the equipment loans.

#### Scenario: Regular user

- **WHEN** a user who is not a manager opens the dashboard
- **THEN** the organizations section comes before the upcoming bookings section and no equipment loans section is shown

#### Scenario: Manager

- **WHEN** a manager opens the dashboard
- **THEN** the equipment loans section is shown after the upcoming bookings section

### Requirement: No breadcrumb

The dashboard SHALL NOT show a breadcrumb.

#### Scenario: Opening the dashboard

- **WHEN** a logged-in user opens the dashboard
- **THEN** no breadcrumb navigation is rendered

### Requirement: Rows link to their detail page

Each organization, booking and equipment loan on the dashboard SHALL be shown as one row that as a whole links to its detail page; there SHALL be no separate details button.

#### Scenario: Organization row

- **WHEN** the user has a booking permission for an organization
- **THEN** the organization's row shows its name and status and links to the organization's detail page

#### Scenario: Booking row

- **WHEN** the user's organization has an upcoming pending or confirmed booking
- **THEN** the booking's row shows the short date (weekday abbreviation, day and month), start and end time, title, resource, organization and status, and links to the booking's detail page

#### Scenario: Equipment loan row

- **WHEN** a manager's organization has a pending or confirmed equipment loan
- **THEN** the loan's row shows the period, the borrowed items with quantities, the organization and the status, and links to the booking group's detail page

### Requirement: Organization groups on organization rows

Each organization row SHALL show the organization's groups that users can choose when creating an organization (`show_on_organization_creation`), sorted by name. Groups that are not selectable on organization creation SHALL NOT be shown.

#### Scenario: Selectable groups shown

- **WHEN** the user's organization belongs to the selectable groups "Self-help group" and "Club member"
- **THEN** the organization's row shows both group names

#### Scenario: Internal groups hidden

- **WHEN** the user's organization also belongs to a group that is not selectable on organization creation
- **THEN** that group's name does not appear on the dashboard

### Requirement: Create actions in section headers

Each section header SHALL offer its create action: "New Organization" for organizations, "New Booking Request" for bookings and "Borrow Equipment" for equipment loans. On narrow screens the action MAY show only its icon but SHALL keep an accessible label.

#### Scenario: Create actions present

- **WHEN** a manager opens the dashboard
- **THEN** the page links to the organization creation, booking creation and item booking creation pages, each with an accessible label

### Requirement: Empty states inside their section

When a section has no entries, the dashboard SHALL show an empty-state message as a row inside that section's card.

#### Scenario: No upcoming bookings

- **WHEN** a user without upcoming bookings opens the dashboard
- **THEN** the upcoming bookings card contains the message "No upcoming bookings"

#### Scenario: No organizations

- **WHEN** a user without booking permissions opens the dashboard
- **THEN** the organizations card contains the message "No organizations yet. Go and add yours!"

### Requirement: Links to all bookings

The upcoming bookings section SHALL link to the full list of bookings and to the list of booking series.

#### Scenario: Footer links

- **WHEN** a logged-in user opens the dashboard
- **THEN** the upcoming bookings card links to the bookings list and the booking series list
