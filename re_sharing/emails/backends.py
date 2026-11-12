"""
Email backend that records every message in the email log (ADR 0028).

It wraps the backend that actually delivers
(``settings.EMAIL_LOG_DELIVERY_BACKEND``) and behaves like it towards the
caller.
"""

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.utils.module_loading import import_string

from re_sharing.emails.services import UNDELIVERED_ERROR
from re_sharing.emails.services import record_email


class LoggingEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, *, alias=None, **kwargs):  # noqa: FBT002
        super().__init__(alias=alias)
        self.fail_silently = fail_silently
        # The delivering backend always raises, so the error can be recorded;
        # fail_silently is honoured here.
        delivery_class = import_string(settings.EMAIL_LOG_DELIVERY_BACKEND)
        self.delivery = delivery_class(**kwargs)

    def open(self):
        return self.delivery.open()

    def close(self):
        return self.delivery.close()

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                delivered = self.delivery.send_messages([message])
            except Exception as error:  # noqa: BLE001
                record_email(message, error=str(error) or type(error).__name__)
                if not self.fail_silently:
                    raise
                continue
            record_email(message, error=None if delivered else UNDELIVERED_ERROR)
            sent += delivered or 0
        return sent
