from datetime import date
from decimal import Decimal

import pytest
from auditlog.models import LogEntry
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import Collection
from re_sharing.agreements.models import SyncState
from re_sharing.agreements.models import UnmatchedReturn
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import CollectionRunFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory


class AgreementKindModelTest(TestCase):
    def test_defaults(self):
        kind = AgreementKindFactory()

        assert kind.is_active
        assert kind.accepting_applications
        assert not kind.requires_deposit
        assert not kind.is_yearly
        assert str(kind) == kind.name

    def test_yearly_kind_requires_collection_month(self):
        kind = MembershipKindFactory.build(collection_month=None)

        with pytest.raises(ValidationError) as error:
            kind.clean()
        assert "collection_month" in error.value.message_dict

    def test_monthly_kind_rejects_collection_month(self):
        kind = AgreementKindFactory.build(collection_month=3)

        with pytest.raises(ValidationError) as error:
            kind.clean()
        assert "collection_month" in error.value.message_dict

    def test_valid_kinds_pass_clean(self):
        AgreementKindFactory.build().clean()
        MembershipKindFactory.build().clean()

    def test_collection_day_limited_to_28(self):
        kind = AgreementKindFactory.build(collection_day=31)

        with pytest.raises(ValidationError):
            kind.clean_fields(exclude=["organization_group", "slug"])


class AgreementModelTest(TestCase):
    def test_defaults_and_str(self):
        agreement = AgreementFactory()

        assert agreement.status == Agreement.Status.SUBMITTED
        assert agreement.details == {}
        assert str(agreement) == f"{agreement.kind} - {agreement.organization}"
        assert str(agreement.uuid) in agreement.get_absolute_url()

    def test_amount_must_be_above_zero(self):
        agreement = AgreementFactory.build(
            kind=AgreementKindFactory(), amount=Decimal(0)
        )

        with pytest.raises(ValidationError) as error:
            agreement.clean()
        assert "amount" in error.value.message_dict

    def test_deposit_rejected_on_kind_without_deposit(self):
        agreement = AgreementFactory.build(
            kind=AgreementKindFactory(requires_deposit=False),
            deposit_amount=Decimal(300),
        )

        with pytest.raises(ValidationError) as error:
            agreement.clean()
        assert "deposit_amount" in error.value.message_dict

    def test_deposit_allowed_on_kind_with_deposit(self):
        agreement = AgreementFactory.build(
            kind=AgreementKindFactory(requires_deposit=True),
            deposit_amount=Decimal(300),
        )

        agreement.clean()

    def test_one_open_agreement_per_organization_and_kind(self):
        agreement = AgreementFactory()

        with pytest.raises(IntegrityError):
            AgreementFactory(organization=agreement.organization, kind=agreement.kind)

    def test_new_agreement_allowed_after_ending(self):
        agreement = AgreementFactory(status=Agreement.Status.ENDED)

        AgreementFactory(organization=agreement.organization, kind=agreement.kind)

    def test_signed_document_completeness(self):
        assert not AgreementFactory().has_complete_signed_document
        assert AgreementFactory(with_signed_document=True).has_complete_signed_document

    def test_active_and_open_mandate(self):
        agreement = AgreementFactory()
        assert agreement.active_mandate is None
        assert agreement.open_mandate is None

        pending = SepaMandateFactory(agreement=agreement, signed_document=None)
        assert agreement.active_mandate is None
        assert agreement.open_mandate == pending

        pending.revoked_on = date(2027, 1, 1)
        pending.save()
        active = SepaMandateFactory(agreement=agreement)
        assert agreement.active_mandate == active
        assert agreement.open_mandate == active


class SepaMandateModelTest(TestCase):
    def test_is_active_requires_signed_document_and_no_revocation(self):
        mandate = SepaMandateFactory()
        assert mandate.is_active

        mandate.revoked_on = date(2027, 5, 1)
        assert not mandate.is_active

        unsigned = SepaMandateFactory(signed_document=None)
        assert not unsigned.is_active

    def test_masked_iban(self):
        mandate = SepaMandateFactory.build(iban="DE89370400440532013000")

        assert mandate.masked_iban.endswith("3000")
        assert "370400" not in mandate.masked_iban
        assert SepaMandateFactory.build(iban="DE89").masked_iban == "DE89"

    def test_str_and_url(self):
        mandate = SepaMandateFactory()

        assert str(mandate) == mandate.reference
        assert str(mandate.uuid) in mandate.get_absolute_url()

    def test_one_open_mandate_per_agreement(self):
        mandate = SepaMandateFactory()

        with pytest.raises(IntegrityError):
            SepaMandateFactory(agreement=mandate.agreement)

    def test_new_mandate_after_revocation(self):
        mandate = SepaMandateFactory(revoked_on=date(2027, 1, 1))

        SepaMandateFactory(agreement=mandate.agreement)

    def test_iban_not_in_audit_log(self):
        mandate = SepaMandateFactory(iban="DE89370400440532013000")
        mandate.iban = "DE02120300000000202051"
        mandate.save()

        for entry in LogEntry.objects.get_for_object(mandate):
            assert "iban" not in (entry.changes or {})
            assert "0532013000" not in str(entry.changes)
            assert "0000202051" not in str(entry.changes)


class CollectionModelTest(TestCase):
    def test_defaults_and_str(self):
        collection = CollectionFactory()

        assert collection.status == Collection.Status.PLANNED
        assert not collection.is_final
        assert collection.reference in str(collection)

    def test_final_statuses(self):
        assert CollectionFactory(status=Collection.Status.PAID).is_final
        assert CollectionFactory(status=Collection.Status.CANCELLED).is_final

    def test_unique_period_per_agreement_and_kind(self):
        collection = CollectionFactory()

        with pytest.raises(IntegrityError):
            CollectionFactory(
                agreement=collection.agreement,
                mandate=collection.mandate,
                period_start=collection.period_start,
            )

    def test_deposit_refund_without_mandate(self):
        collection = CollectionFactory(
            kind=Collection.Kind.DEPOSIT_REFUND, mandate=None
        )

        assert collection.mandate is None


class OtherModelsTest(TestCase):
    def test_str(self):
        run = CollectionRunFactory(count=3)
        state = SyncState.objects.create(
            key="returns", synced_at="2027-03-01T10:00:00+01:00"
        )
        state.refresh_from_db()
        unmatched = UnmatchedReturn.objects.create(
            transaction_id="t1", booked_on=date(2027, 3, 8), amount=Decimal("-60")
        )

        assert str(run) == "2027-03-05 (3)"
        assert str(state).startswith("returns: 2027-03-01")
        assert str(unmatched) == "2027-03-08 -60 €"
