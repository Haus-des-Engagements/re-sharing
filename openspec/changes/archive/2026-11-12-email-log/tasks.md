## 1. Email log app

- [x] 1.1 Create the app `re_sharing.emails` and add it to the installed apps
- [x] 1.2 Tests for `EmailLog`: defaults, entry survives the deletion of its organization, booking and user
- [x] 1.3 Add the `EmailLog` model, a factory and the migration
- [x] 1.4 Tests for the read-only admin: list, search by recipient, no add, change or delete
- [x] 1.5 Register `EmailLog` in the admin

## 2. Logging backend

- [x] 2.1 Tests for `LoggingEmailBackend`: sent entry with recipients, subject, text, HTML and attachment names; failed entry with error and the error raised again; `fail_silently`; several messages in one call; a failing log write does not stop the email
- [x] 2.2 Implement the backend around `EMAIL_LOG_DELIVERY_BACKEND`
- [x] 2.3 Tests for `set_email_log_context`: type and links end up on the entry; an entry passed as `log_entry` is updated instead of a new one created and its attempts are counted
- [x] 2.4 Implement `set_email_log_context` in `emails/services.py` and its use in the backend
- [x] 2.5 Settings: logging backend as `EMAIL_BACKEND` in base, local and production with the previous backend as `EMAIL_LOG_DELIVERY_BACKEND`; a test helper that switches the log on, because the test runner replaces the backend

## 3. Existing emails

- [x] 3.1 Tests: a template email is logged with its type, booking and organization; an account email is logged without them
- [x] 3.2 Set the log context in `send_email_with_template` from the email type and the context
- [x] 3.3 Tests and implementation: the four tasks that build their own message set type and links
- [x] 3.4 Test and fix: `send_email_with_template` adds the BCC only when it is configured

## 4. Spacing and sending again

- [x] 4.1 Add `BULK_EMAIL_SEND_INTERVAL` to the settings (default 5, from the environment)
- [x] 4.2 Tests for `enqueue_spaced`: start times with the interval, interval 0 starts all at once
- [x] 4.3 Implement `enqueue_spaced` in `emails/services.py`
- [x] 4.4 Tests for the custom email view: emails scheduled with the interval, test email immediately, confirmation with count and link to the log
- [x] 4.5 Use `enqueue_spaced` in `send_custom_organization_email_view` and extend the confirmation
- [x] 4.6 Tests for `resend_email`: a failed entry becomes sent with 2 attempts and stored content, stays failed with the new error, a retry is not delivered twice; a sent entry is sent as a new entry and stays unchanged
- [x] 4.7 Implement the task `resend_email` and the service `resend_emails(entries)` that enqueues them spaced

## 5. Pages for managers

- [x] 5.1 View tests for the list: order, pagination, search, filters by status, type, organization and date, manager only
- [x] 5.2 Add the selector, the list view, URL and template; link in the manager navigation
- [x] 5.3 View tests for the email page: fields and content, error on failed entries, notice about attachments, manager only
- [x] 5.4 Add the email page with the HTML content in a sandboxed frame
- [x] 5.5 View tests for sending again: single entry from its page, several selected from the list, failed and sent entries, manager only
- [x] 5.6 Add the two actions (views, URLs, buttons and checkboxes)

## 6. Retention

- [x] 6.1 Add `EMAIL_LOG_RETENTION_MONTHS` to the settings (default 12, from the environment)
- [x] 6.2 Tests for `delete_old_email_logs`: old entries deleted, recent ones kept, number reported
- [x] 6.3 Implement the command

## 7. Documentation and checks

- [x] 7.1 Add ADR 0028 (email log)
- [x] 7.2 README: the cleanup command among the daily commands and the three new environment variables
- [x] 7.3 Add German translations for the new texts
- [x] 7.4 Run the full test suite and pre-commit; check coverage of the changed modules
