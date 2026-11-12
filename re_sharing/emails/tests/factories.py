from factory.django import DjangoModelFactory

from re_sharing.emails.models import EmailLog


class EmailLogFactory(DjangoModelFactory):
    class Meta:
        model = EmailLog

    status = EmailLog.Status.SENT
    from_email = "sender@example.org"
    to = ["recipient@example.org"]
    subject = "Subject"
    body_text = "Text"
    attempts = 1
