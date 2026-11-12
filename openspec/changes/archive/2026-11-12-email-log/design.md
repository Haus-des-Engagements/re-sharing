## Context

Emails are sent in three ways:

- `send_email_with_template` in `organizations/mails.py` builds every email that is based on an `EmailTemplate` from a context that usually contains the booking or the organization. It is called from tasks on the `email` queue in `organizations/mails.py` and `agreements/mails.py`.
- Four tasks in `organizations/mails.py`, among them `send_custom_organization_email`, build their message themselves.
- The login and account emails are sent by the authentication library directly in the web request.

All of them end in the configured `EMAIL_BACKEND` (SMTP in production, console locally, in-memory in tests). A BCC address from the environment is added by our own functions; `send_email_with_template` adds it even when it is not set.

`send_custom_organization_email_view` enqueues one task per selected organization. One worker sends them without a pause. Errors are caught, logged and returned as a value, so the task counts as successful and the manager only sees how many emails were queued.

The task backend supports a delayed start per task.

An earlier draft of this change grouped the emails of a bulk send into batches with pages of their own. That part was dropped: the log with filters and "send again" covers the need with less to build.

## Goals / Non-Goals

**Goals:**

- A complete record of outgoing emails with content, status and error, that can replace the BCC copy.
- Managers can find entries by organization, recipient, type, status and date, read an email as sent and send it again.
- A bulk send does not exceed typical provider limits per minute and does not hold up other emails.
- Tasks that are already queued when this is deployed still run.

**Non-Goals:**

- Masking or leaving out sensitive content.
- Knowing whether an accepted email reached the recipient.
- Grouping the emails of one bulk send; recording emails that were never built.
- Automatic retries.

## Decisions

### D1: A new app `re_sharing.emails`

The log concerns every app that sends email. `EmailLog` gets optional links to organization, booking and user, so the app depends on those apps, and they call a small helper of it. The backend, the pages, the admin and the cleanup command belong together and are not about organizations.

### D2: `EmailLog` model

- `created`, `sent_at`
- `status`: `sent` or `failed`
- `email_type` (free text: the `EmailTemplate` type or a fixed name such as `custom`; empty when unknown)
- `from_email`, `to`, `cc`, `bcc` (lists), `subject`, `body_text`, `body_html`, `attachment_names` (list)
- `error` (text), `attempts`
- `organization`, `booking`, `user`: optional, emptied when the object is deleted, so the entry survives

One entry per message, not per recipient: a message to three people is one entry with three addresses, because the mail server accepts or rejects it as a whole.

### D3: Logging in the email backend

`emails.backends.LoggingEmailBackend` becomes `EMAIL_BACKEND` in production and in local development. It hands each message to the backend named in `EMAIL_LOG_DELIVERY_BACKEND` (SMTP, console or in-memory, as today) and writes the entry: `sent` on success, `failed` with the error text otherwise. Towards the caller it behaves like the wrapped backend: an error is raised again unless `fail_silently` is set, and the number of sent messages is returned.

Alternative considered: logging in our own sending functions. Rejected: the account emails would be missing, and every new sending function would have to remember the log.

A failure to write the log must not stop an email: the backend logs the problem and still sends.

### D4: Type and links travel on the message

`emails.services.set_email_log_context(message, *, email_type="", organization=None, booking=None, user=None, log_entry=None)` stores these values on the message object; the backend reads them. Messages without them (account emails) are logged with content and status only.

`send_email_with_template` sets the type from its `email_type` and takes booking and organization from its context (`context["booking"]` and its organization, or `context["organization"]`), so the many template emails need no change at their call sites. The four tasks that build their own message call the helper themselves.

### D5: Sending again

Every entry can be sent again. The task `resend_email(email_log_id, retry)` on the `email` queue rebuilds the message from the stored fields, with the type and links of the entry.

- **Failed entry (`retry` true):** the entry is passed as `log_entry`, and the backend updates it (status, error, sent time, `attempts` + 1) instead of creating a new one. A failed entry therefore turns into a sent one, and the filter "failed" shows what is still open. If the entry is already `sent` when the task runs, nothing is sent, so a double click or a task run twice cannot deliver the retry twice.
- **Sent entry (`retry` false):** the email is sent as a new email and the backend creates a new entry. The log then shows both deliveries.

Which of the two applies is decided when the manager clicks, from the status of the entry at that moment.

Alternative considered: a new entry for every attempt. Rejected for failed entries: the failed original would stay in the list and nobody could tell whether it was dealt with.

Attachments are not stored, so an email is sent again without them. The page says so when the entry had attachments.

### D6: Spacing

`BULK_EMAIL_SEND_INTERVAL` (seconds, default 5, from the environment). `emails.services.enqueue_spaced(task, argument_lists)` enqueues the *n*-th task with a start time of now + *n* × interval; with 0 all start at once. It is used by the custom email view and by sending several entries again. With the default, 200 emails take about 17 minutes.

Spacing uses delayed starts, not a pause inside the task: the single worker stays free between two emails, so booking confirmations go out in between.

### D7: Pages for managers

In `emails`, under `/emails/`, restricted with the existing manager check:

- **List:** newest first, 50 per page, with date, status, type, organization, recipients and subject. Search over recipients and subject; filters for status, type, organization and a date range. Every entry has a checkbox, and "Send selected again" enqueues the selected ones with the spacing.
- **Email page:** all fields of one entry, the text content, and the HTML content inside a sandboxed frame; for a failed entry the error; the button "Send again" for every entry.

The manager navigation links to the list. After a custom email is sent, the success message links to the list filtered by the type custom.

### D8: Admin

`EmailLog` is registered read-only in the admin (no add, change or delete) with the same search and filters.

### D9: Retention

`EMAIL_LOG_RETENTION_MONTHS` (default 12). The command `delete_old_email_logs` deletes entries created before that, reports their number and is added to the commands the README lists for the daily cron job.

### D10: BCC

`send_email_with_template` adds the BCC only when `DEFAULT_BCC_EMAIL` is set, like the other functions. The BCC is switched off by removing the variable in production.

### D11: Tests

The test runner always replaces `EMAIL_BACKEND` with the in-memory backend, whatever the settings say. Existing tests therefore run without the log. Tests of the log switch the logging backend on around the in-memory backend with a helper (`emails/tests/helpers.py`), so `mail.outbox` keeps working.

### D12: ADR

ADR 0028 records D1, D3, D4, D5 and the decision to store content unmasked with a retention period.

## Risks / Trade-offs

- The log holds access codes and password-reset links for up to 12 months and every manager can read them → accepted for now by decision; the retention is configurable, and masking can be added later per email type because the type is stored.
- Table growth: one row with full content per email → bounded by the retention; attachments are not stored.
- "Sent" means the mail server accepted the message → stated on the pages; bounces still arrive in the sender's mailbox.
- An email whose task is lost before sending leaves no entry, and an organization without an email address is skipped without one → as today; the count of queued emails can be compared with the entries of that time.
- The emails of one bulk send are not grouped → they are found by type, date and status; two sends on the same day are told apart by time.
- An email sent again goes out without its attachments → stated on the page; affects calendar files of booking emails.

## Migration Plan

1. Deploy with the migration and the new settings; `EMAIL_LOG_DELIVERY_BACKEND` takes over the value `DJANGO_EMAIL_BACKEND` had. Tasks already queued run unchanged and their emails are logged.
2. Add `delete_old_email_logs` to the daily cron job.
3. After some weeks of comparing log and BCC mailbox, remove `DJANGO_DEFAULT_BCC_EMAIL` from the production environment.
4. Rollback: revert the deployment; the table can stay.

## Open Questions

- Is 5 seconds the right spacing? It depends on the limit of the mail provider.
- Is 12 months the right retention?
