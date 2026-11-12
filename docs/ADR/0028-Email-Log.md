# 28. Email log

Date: 2026-11-12

## Status

Accepted

## Context

Nobody could see afterwards which emails the platform sent, what they said or whether the mail server accepted them. The only record was a blind copy in a mailbox, which shows neither failures nor the organization or booking an email belongs to. A failed send was only written to the server log. Custom emails to many organizations went out without a pause, so a sending limit of the mail provider could cut a send short unnoticed, and all other emails waited behind it.

Ready-made apps exist for logging emails. They store every message without knowing what it is about, and we want entries linked to organizations and bookings and the option to treat types of email differently later.

## Decision

We keep our own email log in a new app, `re_sharing.emails`.

- **Recorded in the email backend.** `LoggingEmailBackend` is the configured backend. It hands every message to the backend that delivers (SMTP in production) and stores one `EmailLog` entry per message with recipients, subject, text and HTML content, attachment names, status and the error of a failed send. Logging in the backend means no email can bypass the log, including the account emails that are not sent by our own code. A problem while writing the log never stops an email.
- **Type and links travel on the message.** Our sending functions call `set_email_log_context` with the type of email and the organization, booking and user it concerns; the backend reads these from the message. Emails based on an `EmailTemplate` get them from their type and template context in one place.
- **Sending again.** Managers can send any entry again from the log. A failed entry is retried on the same entry, so it turns into a sent one and the filter "failed" shows what is still open. A sent entry is sent as a new email with an entry of its own. Attachments are not stored and therefore not sent again.
- **Spacing.** Emails of a bulk send are scheduled `BULK_EMAIL_SEND_INTERVAL` seconds apart with the delayed start of the task backend, so the single email worker stays free for other emails in between.
- **Content is stored unmasked,** including access codes and password-reset links, and managers can read it. Entries are deleted after `EMAIL_LOG_RETENTION_MONTHS` (12 by default) by a daily command.
- **The blind copy stays optional** and can be switched off once the log is trusted.

We decided against grouping the emails of one bulk send into batches: the log with filters for type, status and date covers the need with less to build.

## Consequences

- There is one place to see what was sent to whom and whether it failed, and to send it again.
- "Sent" means the mail server accepted the message. Bounces still arrive in the sender's mailbox.
- The database holds sensitive email content for the retention period. Masking per email type can be added later, because the type is stored.
- An email whose task is lost before sending, or that is skipped because the organization has no address, leaves no entry.
- The backend uses the `EMAIL_BACKEND` setting, which Django has deprecated in favour of `MAILERS`. Moving the project to `MAILERS` will have to include this backend.
- Tests run without the log by default, because the test runner replaces the email backend; tests of the log switch it on with a helper.
