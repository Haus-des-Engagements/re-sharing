## Why

Nobody can see afterwards which emails the platform sent, what they said or whether the mail server accepted them. The only record is a BCC copy in a mailbox, which shows neither failures nor the organization or booking an email belongs to. A failed send is only written to the server log. For a custom email to around 200 organizations this means that a provider limit can cut the send short without anyone noticing, and that all other emails wait behind it, because the emails go out without a pause.

## What Changes

- **Email log:** every email is stored with recipients, subject, text and HTML content, the names of its attachments, its status (sent or failed) and, when sending failed, the error of the mail server. This includes login and password-reset emails. Content is stored as sent; nothing is masked for now.
- **Links:** an entry carries the type of email (for example booking confirmation or custom email) and is linked to the organization, the booking and the user it concerns, where the sending code knows them.
- **No email bypasses the log:** it is written by the email backend.
- **Page for managers:** a list of the log, newest first, with search by recipient and subject and filters for status, type, organization and date, and a page that shows one email as it was sent.
- **Send again:** a manager can send any email of the log again, failed or sent, one at a time or several selected ones at once. The stored content is sent as it is. A failed email keeps its entry, which then shows the new outcome; sending a sent email again adds a new entry.
- **Spacing setting:** the emails of a custom email to many organizations, and emails that are sent again together, are scheduled a configurable number of seconds apart (default 5), so other emails of the platform go out in between.
- **Admin:** the log is also available read-only in the admin.
- **Retention:** entries older than a configurable number of months (default 12) are deleted by a command that is run daily.
- **BCC:** the copy stays configurable and can be switched off in the environment once the log is trusted. Switching it off currently breaks the template emails; this is fixed.

Out of scope: masking of sensitive content, grouping the emails of one bulk send, recording organizations that were skipped because they have no email address, showing emails on the pages of organizations and bookings, automatic retries, bounce tracking, storing attachment contents.

## Capabilities

### New Capabilities

- `email-log`: recording of every outgoing email with content, status, error and links; manager pages; sending emails again; admin; retention.

### Modified Capabilities

- `organization-custom-email`: the emails of a send are spaced out and the page points to the email log.

## Impact

- New app `re_sharing/emails/`: model `EmailLog`, the logging email backend, a helper to attach type and links to a message, the task that sends an entry again, manager views with URLs and templates, read-only admin, the cleanup command, migration.
- `config/settings/*.py`: the logging backend becomes `EMAIL_BACKEND` and wraps the backend used so far (`EMAIL_LOG_DELIVERY_BACKEND`); new `EMAIL_LOG_RETENTION_MONTHS` and `BULK_EMAIL_SEND_INTERVAL`.
- `re_sharing/organizations/mails.py`, `re_sharing/agreements/mails.py`: messages carry their type and links; the BCC is only set when configured.
- `re_sharing/organizations/views.py` and the custom email template: tasks are scheduled with the interval; the success message links to the log.
- Manager navigation: link to the email log.
- `README.md`: the cleanup command joins the daily commands; new environment variables.
- `docs/ADR/0028-...`: decision record for the email log.
- No new dependency. The task `send_custom_organization_email` keeps its arguments, so tasks queued before the deployment still run.
- The database will hold the content of all emails, including access codes and password-reset links, for the retention period, and managers can read it.
