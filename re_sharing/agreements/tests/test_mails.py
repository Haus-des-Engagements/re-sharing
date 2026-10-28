from datetime import date
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.test import override_settings

from re_sharing.agreements.mails import organization_recipients
from re_sharing.agreements.mails import send_agreement_application_emails
from re_sharing.agreements.mails import send_agreement_approved_email
from re_sharing.agreements.mails import send_agreement_ended_email
from re_sharing.agreements.mails import send_agreement_rejected_email
from re_sharing.agreements.mails import send_pre_notification_email
from re_sharing.agreements.mails import send_return_invoice_email
from re_sharing.agreements.models import Collection
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.organizations.models import EmailTemplate

EmailType = EmailTemplate.EmailTypeChoices
ORGANIZATION_EMAILS = 6
EVERYTHING = (
    "{{ organization }} {{ agreement }} {{ agreement.amount }} {{ kind }} "
    "{{ agreement_url }} {{ mandate_reference }} {{ creditor_id }} "
    "{{ creditor_name }} {{ first_collection }} {{ collection }}"
)


@override_settings(
    DEFAULT_MANAGER_EMAIL="manager@example.com", SEPA_CREDITOR_ID="DE98ZZZ09999999999"
)
class AgreementMailsTest(TestCase):
    def setUp(self):
        for email_type in [
            EmailType.AGREEMENT_APPLICATION_RECEIVED,
            EmailType.MANAGER_NEW_AGREEMENT,
            EmailType.AGREEMENT_APPROVED,
            EmailType.AGREEMENT_REJECTED,
            EmailType.AGREEMENT_ENDED,
            EmailType.AGREEMENT_PRE_NOTIFICATION,
            EmailType.AGREEMENT_RETURN_INVOICE,
        ]:
            EmailTemplate.objects.create(
                email_type=email_type, subject=email_type, body=EVERYTHING, active=True
            )
        self.agreement = AgreementFactory(
            kind=MembershipKindFactory(),
            start_date=date(2027, 10, 10),
            amount=Decimal(60),
        )
        self.mandate = SepaMandateFactory(agreement=self.agreement, iban=VALID_IBAN)
        self.admin = make_admin(self.agreement.organization)
        self.collection = CollectionFactory(
            agreement=self.agreement,
            mandate=self.mandate,
            period_start=date(2027, 11, 1),
            period_end=date(2027, 12, 31),
            amount=Decimal(10),
            invoice_number="RE-1",
        )

    def test_recipients(self):
        send_agreement_application_emails.call(self.agreement.id)
        send_agreement_approved_email.call(self.agreement.id)
        send_agreement_rejected_email.call(self.agreement.id)
        send_agreement_ended_email.call(self.agreement.id)
        send_pre_notification_email.call(self.collection.id)
        send_return_invoice_email.call(self.collection.id)

        recipients = [message.to for message in mail.outbox]
        assert recipients.count([self.admin.email]) == ORGANIZATION_EMAILS
        assert recipients.count(["manager@example.com"]) == 1

    def test_no_email_contains_iban(self):
        send_agreement_application_emails.call(self.agreement.id)
        send_agreement_approved_email.call(self.agreement.id)
        send_pre_notification_email.call(self.collection.id)
        send_return_invoice_email.call(self.collection.id)

        assert mail.outbox
        for message in mail.outbox:
            assert VALID_IBAN not in message.body
            assert VALID_IBAN[-10:] not in message.body
            assert not message.attachments

    def test_approval_email_names_first_period_and_mandate(self):
        send_agreement_approved_email.call(self.agreement.id)

        body = mail.outbox[0].body
        assert self.mandate.reference in body
        assert "10" in body
        assert "DE98ZZZ09999999999" in body

    def test_return_invoice_email_names_invoice(self):
        self.collection.status = Collection.Status.INVOICED
        self.collection.save()

        send_return_invoice_email.call(self.collection.id)

        assert "RE-1" in mail.outbox[0].body

    def test_recipients_fallback_and_organization_only(self):
        organization = AgreementFactory().organization
        assert organization_recipients(organization) == [organization.email]

        organization.send_booking_emails_only_to_organization = True
        make_admin(organization)
        assert organization_recipients(organization) == [organization.email]
