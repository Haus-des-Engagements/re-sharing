from datetime import date
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from re_sharing.agreements.forms import ManagerAgreementEditForm
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import Collection
from re_sharing.agreements.services import AgreementError
from re_sharing.agreements.services import end_agreement
from re_sharing.agreements.services import end_expired_agreements
from re_sharing.agreements.services import manager_update_agreement
from re_sharing.agreements.services import schedule_agreement_end
from re_sharing.agreements.services_collections import create_due_collections
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import EmailTemplate
from re_sharing.organizations.tests.factories import EmailTemplateFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory

EmailType = EmailTemplate.EmailTypeChoices
PLANNED = Collection.Status.PLANNED
NOTIFIED = Collection.Status.NOTIFIED


def _collection(agreement, month, status, mandate):
    start = date(2027, month, 1)
    return CollectionFactory(
        agreement=agreement,
        mandate=mandate,
        period_start=start,
        period_end=start + timedelta(days=27),
        due_date=start + timedelta(days=4),
        status=status,
    )


class EndingTestBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.agreement = AgreementFactory(
            status=Agreement.Status.ACTIVE, start_date=date(2026, 1, 1)
        )
        self.organization = self.agreement.organization
        self.group = self.agreement.kind.organization_group
        self.organization.organization_groups.add(self.group)
        self.mandate = SepaMandateFactory(agreement=self.agreement)
        self.manager = make_manager(self.group)

    def _in_group(self):
        return self.organization.organization_groups.filter(id=self.group.id).exists()


class ScheduleAgreementEndTest(EndingTestBase):
    def test_future_end_keeps_agreement_active(self):
        end = self.today + timedelta(days=60)

        with self.captureOnCommitCallbacks(execute=True):
            schedule_agreement_end(self.manager, self.agreement, end)

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ACTIVE
        assert self.agreement.end_date == end
        assert self._in_group()
        assert mail.outbox == []

    def test_collections_after_end_dropped(self):
        before = _collection(
            self.agreement, 1, Collection.Status.NOTIFIED, self.mandate
        )
        planned = _collection(
            self.agreement, 3, Collection.Status.PLANNED, self.mandate
        )
        notified = _collection(
            self.agreement, 4, Collection.Status.NOTIFIED, self.mandate
        )

        schedule_agreement_end(self.manager, self.agreement, date(2027, 2, 28))

        assert not Collection.objects.filter(id=planned.id).exists()
        notified.refresh_from_db()
        before.refresh_from_db()
        assert notified.status == Collection.Status.CANCELLED
        assert notified.status_note.startswith("The agreement ends on")
        assert before.status == Collection.Status.NOTIFIED

    def test_moving_end_later_recreates_planned_periods(self):
        kind = AgreementKindFactory(collection_day=5)
        agreement = AgreementFactory(
            kind=kind, status=Agreement.Status.ACTIVE, start_date=date(2026, 1, 1)
        )
        SepaMandateFactory(agreement=agreement)
        manager = make_manager(kind.organization_group)
        first = create_due_collections(self.today)
        assert first

        schedule_agreement_end(manager, agreement, self.today + timedelta(days=1))
        assert not agreement.collections_of_agreement.filter(
            period_start__gt=agreement.end_date
        ).exists()

        schedule_agreement_end(manager, agreement, self.today + timedelta(days=365))
        again = create_due_collections(self.today)
        assert {c.period_start for c in again} == {c.period_start for c in first}

    def test_daily_command_ends_after_the_date(self):
        EmailTemplateFactory(
            email_type=EmailType.AGREEMENT_ENDED, active=True, subject="s", body="b"
        )
        end = self.today + timedelta(days=10)
        schedule_agreement_end(self.manager, self.agreement, end)

        assert end_expired_agreements(end) == []
        with self.captureOnCommitCallbacks(execute=True):
            ended = end_expired_agreements(end + timedelta(days=1))

        assert ended == [self.agreement]
        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ENDED
        assert self.agreement.end_date == end
        assert not self._in_group()
        assert len(mail.outbox) == 1

    def test_refused_for_today_past_and_before_start(self):
        for end in [self.today, self.today - timedelta(days=1)]:
            with pytest.raises(AgreementError):
                schedule_agreement_end(self.manager, self.agreement, end)

        self.agreement.start_date = self.today + timedelta(days=30)
        self.agreement.save()
        with pytest.raises(AgreementError):
            schedule_agreement_end(
                self.manager, self.agreement, self.today + timedelta(days=10)
            )

    def test_only_active(self):
        self.agreement.status = Agreement.Status.SUBMITTED
        self.agreement.save()

        with pytest.raises(AgreementError):
            schedule_agreement_end(
                self.manager, self.agreement, self.today + timedelta(days=10)
            )

    def test_out_of_scope_denied(self):
        with pytest.raises(PermissionDenied):
            schedule_agreement_end(
                make_manager(OrganizationGroupFactory()),
                self.agreement,
                self.today + timedelta(days=10),
            )


class EndAgreementDateTest(EndingTestBase):
    def test_given_date_replaces_stored_end_date(self):
        self.agreement.end_date = self.today + timedelta(days=365)
        self.agreement.save()

        end_agreement(self.manager, self.agreement, self.today)

        self.agreement.refresh_from_db()
        assert self.agreement.end_date == self.today

    def test_withdrawn_before_start(self):
        self.agreement.start_date = self.today + timedelta(days=30)
        self.agreement.save()
        planned = _collection(
            self.agreement, 3, Collection.Status.PLANNED, self.mandate
        )

        end_agreement(self.manager, self.agreement)

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ENDED
        assert self.agreement.end_date == self.today
        assert not Collection.objects.filter(id=planned.id).exists()


class EditEndDateTest(EndingTestBase):
    def test_changed_end_date_drops_later_collections(self):
        kind = AgreementKindFactory(requires_end_date=True)
        agreement = AgreementFactory(
            kind=kind,
            status=Agreement.Status.ACTIVE,
            start_date=date(2026, 1, 1),
            end_date=date(2027, 12, 31),
        )
        mandate = SepaMandateFactory(agreement=agreement)
        planned = _collection(agreement, 6, Collection.Status.PLANNED, mandate)
        kept = _collection(agreement, 2, Collection.Status.PLANNED, mandate)
        form = ManagerAgreementEditForm(
            data={
                "start_date": "2026-01-01",
                "end_date": "2027-03-31",
                "amount": str(Decimal(120)),
            },
            agreement=agreement,
        )
        assert form.is_valid(), form.errors

        manager_update_agreement(make_manager(), agreement, form)

        assert not Collection.objects.filter(id=planned.id).exists()
        assert Collection.objects.filter(id=kept.id).exists()
