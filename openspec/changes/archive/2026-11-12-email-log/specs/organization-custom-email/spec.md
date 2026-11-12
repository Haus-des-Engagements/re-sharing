## ADDED Requirements

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
