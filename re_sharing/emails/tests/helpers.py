from django.test import override_settings

LOGGING_BACKEND = "re_sharing.emails.backends.LoggingEmailBackend"
LOCMEM_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# The test runner replaces EMAIL_BACKEND with the in-memory backend. Tests of
# the email log switch the logging backend on around it, so mail.outbox works.
with_email_log = override_settings(
    EMAIL_BACKEND=LOGGING_BACKEND, EMAIL_LOG_DELIVERY_BACKEND=LOCMEM_BACKEND
)


class FailingEmailBackend:
    """Delivering backend whose mail server rejects everything."""

    def __init__(self, *args, **kwargs):
        pass

    def open(self):
        return False

    def close(self):
        pass

    def send_messages(self, email_messages):
        msg = "550 Mailbox unavailable"
        raise ConnectionError(msg)


FAILING_BACKEND = "re_sharing.emails.tests.helpers.FailingEmailBackend"
with_failing_email_log = override_settings(
    EMAIL_BACKEND=LOGGING_BACKEND, EMAIL_LOG_DELIVERY_BACKEND=FAILING_BACKEND
)
