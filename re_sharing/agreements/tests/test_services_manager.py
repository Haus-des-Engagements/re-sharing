import re
from datetime import date
from decimal import Decimal

import pytest
from auditlog.models import LogEntry
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from re_sharing.agreements.forms import ManagerAgreementEditForm
from re_sharing.agreements.forms import ManagerAgreementForm
from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import Collection
from re_sharing.agreements.models import SepaMandate
from re_sharing.agreements.services import AgreementError
from re_sharing.agreements.services import delete_agreement
from re_sharing.agreements.services import manager_create_agreement
from re_sharing.agreements.services import manager_update_agreement
from re_sharing.agreements.services_collections import create_due_collections
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import CoworkingKindFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.resources.models import PermanentCode


def _create_form(kind, organization, **overrides):
    data = {
        "organization": organization.id,
        "status": Agreement.Status.SUBMITTED,
        "start_date": "2026-01-01",
        "amount": "60.00",
    }
    data.update(overrides)
    form = ManagerAgreementForm(data=data, kind=kind)
    assert form.is_valid(), form.errors
    return form


class ManagerCreateAgreementTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory()
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.manager = make_manager(self.kind.organization_group)

    def _create(self, **overrides):
        form = _create_form(self.kind, self.organization, **overrides)
        with self.captureOnCommitCallbacks(execute=True):
            return manager_create_agreement(
                self.manager, self.organization, self.kind, form
            )

    def test_submitted_sends_no_email_and_keeps_groups(self):
        agreement = self._create(notes="Paper application")

        assert agreement.status == Agreement.Status.SUBMITTED
        assert agreement.decided_at is None
        assert agreement.notes == "Paper application"
        assert mail.outbox == []
        assert not self.organization.organization_groups.filter(
            id=self.kind.organization_group_id
        ).exists()

    def test_active_records_decision_and_adds_group_only(self):
        self.kind.accesses.set([])
        agreement = self._create(
            status=Agreement.Status.ACTIVE, decided_at="2025-11-20"
        )

        assert agreement.status == Agreement.Status.ACTIVE
        assert agreement.decided_at == date(2025, 11, 20)
        assert agreement.decided_by == self.manager
        assert self.organization.organization_groups.filter(
            id=self.kind.organization_group_id
        ).exists()
        assert agreement.permanent_code is None
        assert not PermanentCode.objects.exists()
        assert not agreement.collections_of_agreement.exists()
        assert mail.outbox == []

    def test_active_decision_date_defaults_to_today(self):
        agreement = self._create(status=Agreement.Status.ACTIVE)

        assert agreement.decided_at == timezone.localdate()

    def test_active_bills_only_periods_due_after_creation(self):
        kind = AgreementKindFactory(collection_day=5)
        manager = make_manager(kind.organization_group)
        form = _create_form(kind, self.organization, status=Agreement.Status.ACTIVE)
        agreement = manager_create_agreement(manager, self.organization, kind, form)
        SepaMandateFactory(agreement=agreement)

        created = create_due_collections(timezone.localdate())

        assert created
        assert all(
            collection.due_date >= agreement.created.date() for collection in created
        )

    def test_kind_closed_for_applications_allowed(self):
        self.kind.accepting_applications = False
        self.kind.save()

        assert self._create().kind == self.kind

    def test_inactive_kind_refused(self):
        self.kind.is_active = False
        self.kind.save()

        with pytest.raises(AgreementError):
            self._create()

    def test_unconfirmed_organization_refused(self):
        self.organization.status = Organization.Status.PENDING
        self.organization.save()
        form = _create_form(
            self.kind, OrganizationFactory(status=Organization.Status.CONFIRMED)
        )

        with pytest.raises(AgreementError):
            manager_create_agreement(self.manager, self.organization, self.kind, form)

    def test_duplicate_refused(self):
        existing = AgreementFactory(organization=self.organization, kind=self.kind)

        with pytest.raises(AgreementError, match=re.escape(str(existing))):
            self._create()

    def test_out_of_scope_denied(self):
        self.manager = make_manager(OrganizationGroupFactory())

        with pytest.raises(PermissionDenied):
            self._create()

    def test_details_and_signed_document_stored(self):
        kind = CoworkingKindFactory()
        manager = make_manager(kind.organization_group)
        form = ManagerAgreementForm(
            data={
                "organization": self.organization.id,
                "status": Agreement.Status.SUBMITTED,
                "start_date": "2026-01-01",
                "amount": "120",
                "desks": "2",
                "hours_per_week": "10",
                "signed_on": "2025-12-01",
            },
            files={"signed_document": pdf_file()},
            kind=kind,
        )
        assert form.is_valid(), form.errors

        agreement = manager_create_agreement(manager, self.organization, kind, form)

        assert agreement.details == {"desks": 2, "hours_per_week": 10}
        assert agreement.has_complete_signed_document


class ManagerUpdateAgreementTest(TestCase):
    def setUp(self):
        self.kind = CoworkingKindFactory()
        self.agreement = AgreementFactory(
            kind=self.kind,
            status=Agreement.Status.ACTIVE,
            details={"desks": 2, "hours_per_week": 10, "legacy": "kept"},
        )
        self.manager = make_manager(self.kind.organization_group)

    def _form(self, **overrides):
        data = {
            "start_date": "2027-03-01",
            "amount": "150",
            "contact_person_function": "Treasurer",
            "desks": "3",
            "hours_per_week": "10",
            "notes": "Raised",
        }
        data.update(overrides)
        form = ManagerAgreementEditForm(data=data, agreement=self.agreement)
        assert form.is_valid(), form.errors
        return form

    def test_updates_data_and_keeps_other_answers(self):
        manager_update_agreement(self.manager, self.agreement, self._form())

        self.agreement.refresh_from_db()
        assert self.agreement.amount == Decimal(150)
        assert self.agreement.contact_person_function == "Treasurer"
        assert self.agreement.notes == "Raised"
        assert self.agreement.details == {
            "desks": 3,
            "hours_per_week": 10,
            "legacy": "kept",
        }

    def test_existing_collections_keep_amount(self):
        collection = CollectionFactory(agreement=self.agreement, amount=Decimal(120))

        manager_update_agreement(self.manager, self.agreement, self._form())

        collection.refresh_from_db()
        assert collection.amount == Decimal(120)

    def test_deposit_and_end_date_updated_when_kind_has_them(self):
        kind = AgreementKindFactory(requires_deposit=True, requires_end_date=True)
        agreement = AgreementFactory(kind=kind, deposit_amount=Decimal(300))
        form = ManagerAgreementEditForm(
            data={
                "start_date": "2027-03-01",
                "end_date": "2029-02-28",
                "amount": "150",
                "deposit_amount": "450",
            },
            agreement=agreement,
        )
        assert form.is_valid(), form.errors

        manager_update_agreement(make_manager(), agreement, form)

        agreement.refresh_from_db()
        assert agreement.deposit_amount == Decimal(450)
        assert agreement.end_date == date(2029, 2, 28)

    def test_audit_log_records_manager(self):
        manager_update_agreement(self.manager, self.agreement, self._form())

        entry = LogEntry.objects.get_for_object(self.agreement).first()
        assert entry.actor == self.manager
        assert "amount" in entry.changes_dict

    def test_closed_agreement_refused(self):
        self.agreement.status = Agreement.Status.ENDED
        self.agreement.save()

        with pytest.raises(AgreementError):
            manager_update_agreement(self.manager, self.agreement, self._form())

    def test_out_of_scope_denied(self):
        with pytest.raises(PermissionDenied):
            manager_update_agreement(
                make_manager(OrganizationGroupFactory()), self.agreement, self._form()
            )


class DeleteAgreementTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(with_signed_document=True)
        self.mandate = SepaMandateFactory(agreement=self.agreement)
        self.manager = make_manager(self.agreement.kind.organization_group)

    def test_deletes_agreement_mandates_and_files(self):
        documents = [self.agreement.signed_document, self.mandate.signed_document]
        stored = [(document.storage, document.name) for document in documents]
        assert all(storage.exists(name) for storage, name in stored)

        with self.captureOnCommitCallbacks(execute=True):
            delete_agreement(self.manager, self.agreement)

        assert not Agreement.objects.filter(id=self.agreement.id).exists()
        assert not SepaMandate.objects.filter(id=self.mandate.id).exists()
        assert not any(storage.exists(name) for storage, name in stored)

    def test_active_refused(self):
        self.agreement.status = Agreement.Status.ACTIVE
        self.agreement.save()

        with pytest.raises(AgreementError):
            delete_agreement(self.manager, self.agreement)

    def test_with_collection_refused(self):
        CollectionFactory(agreement=self.agreement, mandate=self.mandate)

        with pytest.raises(AgreementError):
            delete_agreement(self.manager, self.agreement)
        assert Collection.objects.filter(agreement=self.agreement).exists()

    def test_out_of_scope_denied(self):
        with pytest.raises(PermissionDenied):
            delete_agreement(make_manager(OrganizationGroupFactory()), self.agreement)
