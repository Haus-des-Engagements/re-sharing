## ADDED Requirements

### Requirement: Every outgoing email is recorded

Every email the platform hands to its email backend SHALL be recorded as one entry with the sender address, the recipients (to, cc and bcc), the subject, the text content, the HTML content where the email has one, the file names of its attachments and the time. This SHALL include emails that are not sent by the platform's own tasks, such as account emails. Content SHALL be stored as sent.

#### Scenario: Template email is recorded

- **WHEN** a booking confirmation is sent to a user
- **THEN** one entry exists with the user's address as recipient, the rendered subject and the rendered text
- **AND** the name of the attached calendar file is recorded, not its content

#### Scenario: HTML email is recorded with both parts

- **WHEN** a custom email with formatting is sent
- **THEN** its entry holds the text content and the HTML content

#### Scenario: Account email is recorded

- **WHEN** a password-reset email is sent
- **THEN** one entry exists with the recipient, the subject and the content of that email

#### Scenario: Several recipients

- **WHEN** one email is addressed to three recipients
- **THEN** one entry exists that lists the three addresses

### Requirement: Entries record the outcome

An entry SHALL have the status sent with a sent time when the delivering backend accepted the email, and failed with the error message when it raised an error. Recording SHALL NOT change what the caller experiences: an error is raised to the caller as without the log, and a problem while writing the entry SHALL NOT prevent the email from being sent.

#### Scenario: Accepted email

- **WHEN** the delivering backend accepts an email
- **THEN** its entry is sent and has a sent time

#### Scenario: Rejected email

- **WHEN** the delivering backend raises an error for an email
- **THEN** its entry is failed and its error contains the message of that error
- **AND** the error reaches the caller

#### Scenario: Log cannot be written

- **WHEN** writing the entry fails
- **THEN** the email is still handed to the delivering backend

### Requirement: Entries are linked to what they concern

An entry SHALL carry the type of the email and links to the organization, the booking and the user it concerns where the sending code provides them. Emails based on an email template SHALL get the template's type and the booking and organization of their context. An entry SHALL remain when a linked object is deleted.

#### Scenario: Booking email

- **WHEN** an email about a booking is sent from an email template
- **THEN** its entry has the type of that template, the booking and the booking's organization

#### Scenario: Custom email

- **WHEN** a custom email is sent to an organization
- **THEN** its entry has the type custom and that organization

#### Scenario: Email without context

- **WHEN** an account email is sent
- **THEN** its entry has no type, organization or booking

#### Scenario: Linked booking is deleted

- **WHEN** the booking of an entry is deleted
- **THEN** the entry still exists without a booking

### Requirement: Managers can browse the email log

A page for managers SHALL list the entries, newest first and 50 per page with links to the other pages, with date, status, type, organization, recipients and subject. It SHALL offer a search over recipients and subject and filters for status, type, organization and a date range. A second page SHALL show one entry as it was sent: its fields, the text content, the HTML content and, for a failed entry, the error. Both pages SHALL be available to managers only, and the manager navigation SHALL link to the list.

#### Scenario: List shows recent emails

- **WHEN** a manager opens the email log after two emails were sent
- **THEN** both are listed, the newer one first

#### Scenario: More entries than fit on a page

- **WHEN** the log holds 60 entries and a manager opens the email log
- **THEN** the 50 newest are listed with a link to the second page
- **AND** the second page lists the remaining 10 and keeps the active filters

#### Scenario: Filter by status

- **WHEN** a manager filters the log by the status failed
- **THEN** only failed entries are listed

#### Scenario: Search by recipient

- **WHEN** a manager searches the log for an address
- **THEN** only entries sent to that address are listed

#### Scenario: Filter by organization

- **WHEN** a manager filters the log by an organization
- **THEN** only entries linked to that organization are listed

#### Scenario: Email as sent

- **WHEN** a manager opens an entry
- **THEN** its subject, recipients and content are shown

#### Scenario: Failed email shows the error

- **WHEN** a manager opens a failed entry
- **THEN** the error of the mail server is shown

#### Scenario: Not a manager

- **WHEN** a user who is not a manager requests the email log or an entry
- **THEN** access is denied

### Requirement: Emails can be sent again

A manager SHALL be able to send any entry again from its page, and several selected entries at once from the list. The stored recipients, subject and content SHALL be sent unchanged, without attachments. For a failed entry, the same entry SHALL record the new outcome and count the attempt, and no second entry SHALL be created. For a sent entry, the email SHALL be recorded as a new entry with the same type and links, and the original entry SHALL stay unchanged.

#### Scenario: Failed email succeeds on the second attempt

- **WHEN** a manager sends a failed entry again and the mail server accepts the email
- **THEN** the same entry is sent, has no error and counts 2 attempts
- **AND** the email has the stored recipients, subject and content

#### Scenario: Failed email fails again

- **WHEN** the mail server rejects the email again
- **THEN** the entry stays failed with the new error and counts 2 attempts

#### Scenario: Retry is not delivered twice

- **WHEN** the retry of a failed entry runs a second time after the entry became sent
- **THEN** no email is sent

#### Scenario: Sent email is sent again

- **WHEN** a manager sends a sent entry again
- **THEN** an email with the stored recipients, subject and content is sent
- **AND** a new entry with the same type and organization exists
- **AND** the original entry is unchanged

#### Scenario: Several entries at once

- **WHEN** a manager selects 3 entries and sends them again
- **THEN** 3 emails are scheduled with the configured interval between them

#### Scenario: Entry with attachments

- **WHEN** a manager opens an entry that had an attachment
- **THEN** the page states that the email is sent again without its attachment

### Requirement: Staff can read the log in the admin

The admin SHALL list the entries with the same search and filters. Entries SHALL NOT be added, changed or deleted there.

#### Scenario: Entries cannot be edited

- **WHEN** a staff member opens an entry in the admin
- **THEN** its fields cannot be changed and no entry can be added

### Requirement: Old entries are deleted

A command SHALL delete the entries created more than a configurable number of months ago, 12 by default, and report how many it deleted.

#### Scenario: Entry older than the retention period

- **WHEN** the command runs with a retention of 12 months and an entry is 13 months old
- **THEN** that entry is deleted

#### Scenario: Recent entry

- **WHEN** the command runs and an entry is 11 months old
- **THEN** that entry is kept

### Requirement: The blind copy is optional for every email

A blind copy SHALL be added to an email only when a blind-copy address is configured.

#### Scenario: No address configured

- **WHEN** no blind-copy address is configured and an email based on an email template is sent
- **THEN** the email is sent without a blind copy
