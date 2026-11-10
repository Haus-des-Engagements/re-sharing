## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Page help lists the available template tags

The page SHALL document the available email template tags: `organization.name`, `organization.email`, `number_of_bookings`, `total_amount`, `from_date`, `to_date`, `domain`, and SHALL NOT mention `months`. The help SHALL state that template tags can be used inside link targets.

#### Scenario: Help text after preview
- **WHEN** a manager previews organizations
- **THEN** the compose section lists `from_date`, `to_date` and `domain` as template tags and does not list `months`
