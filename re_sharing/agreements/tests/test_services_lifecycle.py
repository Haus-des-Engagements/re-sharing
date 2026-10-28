from datetime import date
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from re_sharing.agreements.forms import ApplicationForm
from re_sharing.agreements.forms import SignedDocumentForm
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import Collection
from re_sharing.agreements.services import AgreementError
from re_sharing.agreements.services import approve_agreement
from re_sharing.agreements.services import create_agreement
from re_sharing.agreements.services import end_agreement
from re_sharing.agreements.services import end_expired_agreements
from re_sharing.agreements.services import reject_agreement
from re_sharing.agreements.services import upload_signed_document
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import CoworkingKindFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_booker
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import EmailTemplate
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import EmailTemplateFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.models import PermanentCode
from re_sharing.resources.tests.factories import AccessFactory
from re_sharing.resources.tests.factories import PermanentCodeFactory

EmailType = EmailTemplate.EmailTypeChoices


def _templates(*types):
    for email_type in types:
        EmailTemplateFactory(
            email_type=email_type,
            subject=f"{email_type} {{{{ kind.name }}}}",
            body=(
                "{{ agreement.amount }} {{ mandate_reference }} "
                "{{ first_collection.amount }} {{ first_collection.due_date }}"
            ),
        )


def _membership_form(kind, **overrides):
    data = {
        "start_date": "2027-10-10",
        "amount": "60.00",
        "contact_person_function": "Treasurer",
    }
    data.update(overrides)
    form = ApplicationForm(data=data, kind=kind)
    assert form.is_valid(), form.errors
    return form


@override_settings(DEFAULT_MANAGER_EMAIL="manager@example.com")
class CreateAgreementTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.admin = make_admin(self.organization)

    def test_confirmed_admin_applies(self):
        _templates(
            EmailType.AGREEMENT_APPLICATION_RECEIVED, EmailType.MANAGER_NEW_AGREEMENT
        )

        with self.captureOnCommitCallbacks(execute=True):
            agreement = create_agreement(
                self.admin, self.organization, self.kind, _membership_form(self.kind)
            )

        assert agreement.status == Agreement.Status.SUBMITTED
        assert agreement.amount == Decimal("60.00")
        assert agreement.contact_person_function == "Treasurer"
        assert agreement.contact_person == self.admin
        recipients = [message.to for message in mail.outbox]
        assert [self.admin.email] in recipients
        assert ["manager@example.com"] in recipients

    def test_details_stored(self):
        kind = CoworkingKindFactory()
        form = ApplicationForm(
            data={
                "start_date": "2027-03-01",
                "amount": "120",
                "contact_person_function": "Chair",
                "desks": "2",
                "hours_per_week": "20",
            },
            kind=kind,
        )
        assert form.is_valid(), form.errors

        agreement = create_agreement(self.admin, self.organization, kind, form)

        assert agreement.details == {"desks": 2, "hours_per_week": 20}

    def test_with_signed_document(self):
        form = ApplicationForm(
            data={
                "start_date": "2027-10-10",
                "amount": "60",
                "contact_person_function": "Chair",
                "signed_on": "2027-10-01",
            },
            files={"signed_document": pdf_file()},
            kind=self.kind,
        )
        assert form.is_valid(), form.errors

        agreement = create_agreement(self.admin, self.organization, self.kind, form)

        assert agreement.has_complete_signed_document
        assert agreement.signed_on == date(2027, 10, 1)

    def test_booker_denied(self):
        booker = make_booker(self.organization)

        with pytest.raises(PermissionDenied):
            create_agreement(
                booker, self.organization, self.kind, _membership_form(self.kind)
            )

    def test_unconfirmed_organizations_refused(self):
        for status in [
            Organization.Status.PENDING,
            Organization.Status.REJECTED,
            Organization.Status.DEACTIVATED,
        ]:
            self.organization.status = status
            self.organization.save()

            with pytest.raises(AgreementError, match="confirmed"):
                create_agreement(
                    self.admin,
                    self.organization,
                    self.kind,
                    _membership_form(self.kind),
                )

    def test_closed_kinds_refused(self):
        for kind in [
            MembershipKindFactory(is_active=False),
            MembershipKindFactory(accepting_applications=False),
        ]:
            with pytest.raises(AgreementError):
                create_agreement(
                    self.admin, self.organization, kind, _membership_form(kind)
                )

    def test_duplicate_refused(self):
        existing = AgreementFactory(organization=self.organization, kind=self.kind)

        with pytest.raises(AgreementError, match=str(existing.kind)):
            create_agreement(
                self.admin, self.organization, self.kind, _membership_form(self.kind)
            )


class UploadSignedDocumentTest(TestCase):
    def _form(self):
        form = SignedDocumentForm(
            data={"signed_on": "2027-02-01"}, files={"signed_document": pdf_file()}
        )
        assert form.is_valid()
        return form

    def test_admin_uploads(self):
        agreement = AgreementFactory()
        admin = make_admin(agreement.organization)

        upload_signed_document(admin, agreement, self._form())

        agreement.refresh_from_db()
        assert agreement.has_complete_signed_document
        assert agreement.signed_on == date(2027, 2, 1)

    def test_manager_uploads(self):
        agreement = AgreementFactory()

        upload_signed_document(make_manager(), agreement, self._form())

        assert agreement.has_complete_signed_document

    def test_foreign_user_denied(self):
        agreement = AgreementFactory()

        with pytest.raises(PermissionDenied):
            upload_signed_document(
                make_booker(agreement.organization), agreement, self._form()
            )

    def test_closed_agreement_refused(self):
        agreement = AgreementFactory(status=Agreement.Status.REJECTED)

        with pytest.raises(AgreementError):
            upload_signed_document(make_manager(), agreement, self._form())


@override_settings(PRE_NOTIFICATION_DAYS=14)
@patch("re_sharing.resources.services_permanent_code.send_permanent_code_created_email")
class ApproveAgreementTest(TestCase):
    def setUp(self):
        self.access_a = AccessFactory(name="Door A", slug="door-a")
        self.access_b = AccessFactory(name="Door B", slug="door-b")
        self.kind = AgreementKindFactory(
            requires_deposit=True, accesses=[self.access_a, self.access_b]
        )
        self.agreement = AgreementFactory(
            kind=self.kind,
            with_signed_document=True,
            deposit_amount=Decimal(360),
            start_date=date(2027, 3, 20),
        )
        SepaMandateFactory(agreement=self.agreement)
        self.manager = make_manager(self.kind.organization_group)

    def test_approval_effects(self, mock_code_email):
        status_before = self.agreement.organization.status
        _templates(EmailType.AGREEMENT_APPROVED)

        with self.captureOnCommitCallbacks(execute=True):
            approve_agreement(self.manager, self.agreement, date(2027, 3, 10))

        self.agreement.refresh_from_db()
        organization = self.agreement.organization
        organization.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ACTIVE
        assert self.agreement.decided_at == date(2027, 3, 10)
        assert self.agreement.decided_by == self.manager
        assert organization.status == status_before
        assert organization.organization_groups.filter(
            id=self.kind.organization_group_id
        ).exists()
        code = self.agreement.permanent_code
        assert set(code.accesses.all()) == {self.access_a, self.access_b}
        mock_code_email.enqueue.assert_called_once_with(code.id)
        deposit = self.agreement.collections_of_agreement.get(
            kind=Collection.Kind.DEPOSIT
        )
        assert deposit.amount == Decimal(360)
        assert deposit.due_date == date(2027, 3, 20)
        first = self.agreement.collections_of_agreement.get(kind=Collection.Kind.FEE)
        assert first.amount == Decimal("46.45")
        assert first.due_date == date(2027, 3, 24)
        assert first.status == Collection.Status.NOTIFIED
        body = mail.outbox[-1].body
        assert "46.45" in body
        assert self.agreement.active_mandate.reference in body

    def test_kind_without_accesses_creates_no_code(self, mock_code_email):
        self.kind.accesses.clear()

        approve_agreement(self.manager, self.agreement, date(2027, 3, 10))

        assert self.agreement.permanent_code is None
        assert not PermanentCode.objects.exists()

    def test_refused_without_signed_document(self, mock_code_email):
        self.agreement.signed_document = None
        self.agreement.save()

        with pytest.raises(AgreementError, match="contract"):
            approve_agreement(self.manager, self.agreement, date(2027, 3, 10))

    def test_refused_without_mandate(self, mock_code_email):
        self.agreement.mandates_of_agreement.all().delete()

        with pytest.raises(AgreementError, match="SEPA mandate is missing"):
            approve_agreement(self.manager, self.agreement, date(2027, 3, 10))

    def test_refused_with_unsigned_mandate(self, mock_code_email):
        mandate = self.agreement.mandates_of_agreement.get()
        mandate.signed_document = None
        mandate.save()

        with pytest.raises(AgreementError, match="signed SEPA mandate"):
            approve_agreement(self.manager, self.agreement, date(2027, 3, 10))

    def test_refused_outside_scope(self, mock_code_email):
        other = make_manager(OrganizationGroupFactory())

        with pytest.raises(PermissionDenied):
            approve_agreement(other, self.agreement, date(2027, 3, 10))

    def test_non_manager_denied(self, mock_code_email):
        with pytest.raises(PermissionDenied):
            approve_agreement(
                make_admin(self.agreement.organization),
                self.agreement,
                date(2027, 3, 10),
            )

    def test_refused_when_not_submitted(self, mock_code_email):
        self.agreement.status = Agreement.Status.ACTIVE
        self.agreement.save()

        with pytest.raises(AgreementError):
            approve_agreement(self.manager, self.agreement, date(2027, 3, 10))
        with pytest.raises(AgreementError):
            reject_agreement(self.manager, self.agreement, date(2027, 3, 10))


class ApproveMembershipTest(TestCase):
    def test_membership_in_october_gets_two_twelfths_and_no_code(self):
        kind = MembershipKindFactory()
        agreement = AgreementFactory(
            kind=kind,
            amount=Decimal(60),
            start_date=date(2027, 10, 10),
            with_signed_document=True,
        )
        SepaMandateFactory(agreement=agreement)

        approve_agreement(make_manager(), agreement, date(2027, 10, 12))

        first = agreement.collections_of_agreement.get()
        assert first.amount == Decimal("10.00")
        assert first.period_start == date(2027, 11, 1)
        assert first.due_date == date(2027, 10, 26)
        assert agreement.permanent_code is None
        assert not agreement.collections_of_agreement.filter(
            kind=Collection.Kind.DEPOSIT
        ).exists()


class RejectAgreementTest(TestCase):
    def test_reject(self):
        _templates(EmailType.AGREEMENT_REJECTED)
        agreement = AgreementFactory()
        admin = make_admin(agreement.organization)
        groups_before = set(agreement.organization.organization_groups.all())

        with self.captureOnCommitCallbacks(execute=True):
            reject_agreement(make_manager(), agreement, date(2027, 2, 1))

        agreement.refresh_from_db()
        assert agreement.status == Agreement.Status.REJECTED
        assert agreement.decided_at == date(2027, 2, 1)
        assert agreement.organization.status == Organization.Status.CONFIRMED
        assert set(agreement.organization.organization_groups.all()) == groups_before
        assert not agreement.collections_of_agreement.exists()
        assert mail.outbox[-1].to == [admin.email]


class EndAgreementTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(status=Agreement.Status.ACTIVE)
        self.organization = self.agreement.organization
        self.group = self.agreement.kind.organization_group
        self.organization.organization_groups.add(self.group)
        self.manager = make_manager()

    def test_end_defaults_to_today_and_removes_group(self):
        _templates(EmailType.AGREEMENT_ENDED)

        with self.captureOnCommitCallbacks(execute=True):
            end_agreement(self.manager, self.agreement)

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ENDED
        assert self.agreement.end_date == timezone.localdate()
        assert not self.organization.organization_groups.filter(
            id=self.group.id
        ).exists()
        assert len(mail.outbox) == 1

    def test_group_kept_for_other_active_agreement(self):
        other_kind = AgreementKindFactory(organization_group=self.group)
        AgreementFactory(
            organization=self.organization,
            kind=other_kind,
            status=Agreement.Status.ACTIVE,
        )

        end_agreement(self.manager, self.agreement)

        assert self.organization.organization_groups.filter(id=self.group.id).exists()

    def test_code_validity_end_set(self):
        code = PermanentCodeFactory(organization=self.organization)
        self.agreement.permanent_code = code
        self.agreement.save()

        end_agreement(self.manager, self.agreement, date(2027, 6, 30))

        code.refresh_from_db()
        assert timezone.localtime(code.validity_end).date() == date(2027, 6, 30)

    def test_without_code_nothing_touched(self):
        code = PermanentCodeFactory(organization=self.organization)

        end_agreement(self.manager, self.agreement, date(2027, 6, 30))

        code.refresh_from_db()
        assert code.validity_end is None

    def test_later_planned_collections_cancelled(self):
        later = CollectionFactory(
            agreement=self.agreement,
            period_start=date(2027, 7, 1),
            period_end=date(2027, 7, 31),
            status=Collection.Status.NOTIFIED,
        )
        earlier = CollectionFactory(
            agreement=self.agreement,
            mandate=later.mandate,
            period_start=date(2027, 6, 1),
            period_end=date(2027, 6, 30),
        )

        end_agreement(self.manager, self.agreement, date(2027, 6, 30))

        later.refresh_from_db()
        earlier.refresh_from_db()
        assert later.status == Collection.Status.CANCELLED
        assert earlier.status == Collection.Status.PLANNED

    def test_deposit_refund_created_for_paid_deposit(self):
        CollectionFactory(
            agreement=self.agreement,
            kind=Collection.Kind.DEPOSIT,
            amount=Decimal(360),
            status=Collection.Status.COLLECTED,
        )

        end_agreement(self.manager, self.agreement, date(2027, 6, 30))

        refund = self.agreement.collections_of_agreement.get(
            kind=Collection.Kind.DEPOSIT_REFUND
        )
        assert refund.amount == Decimal(360)
        assert refund.status == Collection.Status.PLANNED
        assert refund.mandate is None
        assert refund.reference is None

    def test_no_refund_without_paid_deposit(self):
        end_agreement(self.manager, self.agreement, date(2027, 6, 30))

        assert not self.agreement.collections_of_agreement.filter(
            kind=Collection.Kind.DEPOSIT_REFUND
        ).exists()

    def test_only_active_agreements(self):
        self.agreement.status = Agreement.Status.SUBMITTED
        self.agreement.save()

        with pytest.raises(AgreementError):
            end_agreement(self.manager, self.agreement)

    def test_out_of_scope_denied(self):
        with pytest.raises(PermissionDenied):
            end_agreement(make_manager(OrganizationGroupFactory()), self.agreement)

    def test_expired_agreements_ended(self):
        self.agreement.end_date = timezone.localdate() - timedelta(days=1)
        self.agreement.save()
        current = AgreementFactory(
            status=Agreement.Status.ACTIVE, end_date=timezone.localdate()
        )

        ended = end_expired_agreements(timezone.localdate())

        current.refresh_from_db()
        assert ended == [self.agreement]
        assert current.status == Agreement.Status.ACTIVE

    def test_command(self):
        self.agreement.end_date = timezone.localdate() - timedelta(days=1)
        self.agreement.save()
        out = StringIO()

        call_command("end_expired_agreements", stdout=out)

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ENDED
        assert "Ended 1" in out.getvalue()
