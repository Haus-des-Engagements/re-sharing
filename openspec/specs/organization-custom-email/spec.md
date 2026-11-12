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

The page SHALL document the available email template tags: `organization.name`, `organization.email`, `number_of_bookings`, `total_amount`, `from_date`, `to_date`, `domain`, and SHALL NOT mention `months`. The help SHALL state that template tags can be used inside link targets.

#### Scenario: Help text after preview
- **WHEN** a manager previews organizations
- **THEN** the compose section lists `from_date`, `to_date` and `domain` as template tags and does not list `months`

### Requirement: Body is composed with basic formatting

The compose section SHALL offer a rich-text editor for the body that supports bold, italic, bulleted lists, numbered lists and links, and no other formatting. The subject SHALL remain a plain text field. The system SHALL reject a send or test-send whose body contains no text.

#### Scenario: Editor is shown after preview
- **WHEN** a manager previews organizations
- **THEN** the compose section renders the body field as a rich-text editor and loads the editor assets

#### Scenario: Body with only empty markup is rejected
- **WHEN** the send request carries the body `<p></p>`
- **THEN** no email is enqueued and an error message is shown

### Requirement: Custom emails are sent as HTML with a plain-text alternative

Each custom email SHALL be sent as a multipart message with a plain-text part and an HTML part. The HTML part SHALL contain the formatted body inside a minimal wrapper without branding. The plain-text part SHALL be derived from the same rendered body: paragraphs and line breaks become line breaks, list items are prefixed with `- ` (bulleted) or their number (numbered), and a link is written as its text followed by its URL in parentheses, or as the URL alone when text and URL are identical.

#### Scenario: Both parts are present
- **WHEN** a custom email with body `<p>Hello <strong>all</strong></p>` is sent
- **THEN** the message has an HTML alternative containing `<strong>all</strong>` and a plain-text body containing `Hello all`

#### Scenario: Link keeps its URL in plain text
- **WHEN** the body contains `<a href="https://example.org/x">our page</a>`
- **THEN** the plain-text part contains `our page (https://example.org/x)`

#### Scenario: Lists keep their markers in plain text
- **WHEN** the body contains `<ul><li>one</li><li>two</li></ul>`
- **THEN** the plain-text part contains the lines `- one` and `- two`

#### Scenario: Numbered lists are numbered in plain text
- **WHEN** the body contains `<ol><li>one</li><li>two</li></ol>`
- **THEN** the plain-text part contains the lines `1. one` and `2. two`

### Requirement: Template values are escaped in the HTML part

Values inserted through template tags SHALL be HTML-escaped in the HTML part and SHALL appear unescaped in the plain-text part and in the subject.

#### Scenario: Organization name with markup characters
- **WHEN** an organization is named `A & B <Team>` and subject and body both contain `{{ organization.name }}`
- **THEN** the HTML part contains `A &amp; B &lt;Team&gt;`, and the plain-text part and the subject contain `A & B <Team>`

### Requirement: Body HTML is restricted to the allowed formatting

The system SHALL reduce the rendered body server-side to the elements `p`, `br`, `strong`, `b`, `em`, `i`, `ul`, `ol`, `li` and `a` (with `href` and `target`), and SHALL only keep link targets using `http`, `https` or `mailto`. Other elements and attributes SHALL be removed regardless of what the editor submitted.

#### Scenario: Script is removed
- **WHEN** the submitted body contains `<script>alert(1)</script><p>Hi</p>`
- **THEN** the HTML part contains `<p>Hi</p>` and no `script` element

#### Scenario: Unsafe link target is removed
- **WHEN** the submitted body contains `<a href="javascript:alert(1)">x</a>`
- **THEN** the HTML part contains no `javascript:` link target

#### Scenario: Event handler attribute is removed
- **WHEN** the submitted body contains `<p onclick="x()">Hi</p>`
- **THEN** the HTML part contains `<p>Hi</p>`

### Requirement: Template tags work in text and in link targets

Template tags SHALL be resolved in running text and inside link targets. This SHALL hold when the editor submitted the tag HTML-entity-encoded or, inside a link target, percent-encoded.

#### Scenario: Tag in link target
- **WHEN** the body contains `<a href="https://{{ domain }}/organizations/{{ organization.slug }}/">Profile</a>`
- **THEN** the link target in the HTML part is the URL with domain and slug filled in, and the plain-text part contains that same URL

#### Scenario: Percent-encoded tag in link target
- **WHEN** the body contains `<a href="https://%7B%7B%20domain%20%7D%7D/x">Link</a>`
- **THEN** the link target in the HTML part is `https://<domain>/x` with the site domain filled in

#### Scenario: Entity-encoded quotes inside a tag
- **WHEN** the body contains `{{ total_amount|floatformat:&quot;2&quot; }}`
- **THEN** the tag is rendered as the amount with two decimals

### Requirement: Manager can send a test email to a chosen address

The compose section SHALL offer a test-send with a recipient address field, prefilled with the manager's own email address. A test-send SHALL deliver one email to the entered address only, rendered with the same subject, body, filter context and statistics as the real email for the first selected organization that matches the submitted filters. The test email SHALL have its subject prefixed with `[Test] `, SHALL NOT be sent to any organization and SHALL NOT carry a BCC. The test-send endpoint SHALL be accessible only to managers. After a test-send the page SHALL keep the composed subject, body, filters and organization selection, and SHALL report which address and organization the test was sent for.

#### Scenario: Test email goes only to the entered address
- **WHEN** a manager selects organizations X and Y, enters `me@example.org` and triggers the test-send
- **THEN** exactly one email is enqueued, addressed to `me@example.org` only, without BCC, rendered with the data of X, and no email is addressed to X or Y

#### Scenario: Test subject is marked
- **WHEN** the subject is `Hello {{ organization.name }}` and the test is rendered for organization X
- **THEN** the test email subject is `[Test] Hello X`

#### Scenario: Invalid address is rejected
- **WHEN** the test-send is triggered with `not-an-address` as recipient
- **THEN** no email is enqueued and an error is shown

#### Scenario: Missing address is rejected
- **WHEN** the test-send is triggered with an empty recipient
- **THEN** no email is enqueued and an error is shown

#### Scenario: No organization selected
- **WHEN** the test-send is triggered without any selected organization
- **THEN** no email is enqueued and an error is shown

#### Scenario: Draft survives the test-send
- **WHEN** a manager triggers a test-send from a composed draft
- **THEN** the response updates only a result area and the subject, body, filters and selection remain on the page

#### Scenario: Non-manager is denied
- **WHEN** a logged-in non-manager posts to the test-send endpoint
- **THEN** the request is rejected as it is for other manager-only pages

#### Scenario: Real send is unaffected by the test address
- **WHEN** a manager sends the email to the selected organizations while the test recipient field is filled
- **THEN** one email per selected organization is enqueued and none is addressed to the test recipient

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

### Requirement: Emails of a send are spaced out

The emails of a custom email to the selected organizations SHALL be scheduled one after another with a configurable interval in seconds between them, 5 by default. An interval of 0 SHALL schedule all of them immediately. Test emails SHALL be sent immediately.

#### Scenario: Default spacing

- **WHEN** a manager sends a custom email to 3 organizations at 10:00:00 with an interval of 5 seconds
- **THEN** the emails are scheduled for 10:00:00, 10:00:05 and 10:00:10

#### Scenario: Spacing switched off

- **WHEN** a custom email is sent with an interval of 0
- **THEN** all its emails are scheduled immediately

#### Scenario: Test email

- **WHEN** a manager sends a test email
- **THEN** it is scheduled immediately

### Requirement: The send confirmation points to the email log

After a custom email is sent to the selected organizations, the confirmation SHALL state how many emails were scheduled and link to the email log filtered by custom emails.

#### Scenario: Link after sending

- **WHEN** a manager sends a custom email to 3 organizations
- **THEN** the confirmation states that 3 emails were scheduled
- **AND** it links to the email log showing custom emails
