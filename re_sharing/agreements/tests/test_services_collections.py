from datetime import date
from datetime import datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from xml.etree import ElementTree

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import Collection
from re_sharing.agreements.models import CollectionRun
from re_sharing.agreements.models import SyncState
from re_sharing.agreements.models import UnmatchedReturn
from re_sharing.agreements.services import AgreementError
from re_sharing.agreements.services_collections import RETURNS_SYNC_KEY
from re_sharing.agreements.services_collections import build_collection_run
from re_sharing.agreements.services_collections import build_return_invoice_payload
from re_sharing.agreements.services_collections import cancel_collection
from re_sharing.agreements.services_collections import create_due_collections
from re_sharing.agreements.services_collections import create_first_period_collection
from re_sharing.agreements.services_collections import delete_collection_run
from re_sharing.agreements.services_collections import detect_returns
from re_sharing.agreements.services_collections import invoice_returned_collection
from re_sharing.agreements.services_collections import mark_collected
from re_sharing.agreements.services_collections import mark_collection_paid
from re_sharing.agreements.services_collections import mark_run_uploaded
from re_sharing.agreements.services_collections import next_billing_periods
from re_sharing.agreements.services_collections import notify_due_collections
from re_sharing.agreements.services_collections import sync_invoice_payments
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import CollectionRunFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import EmailTemplate
from re_sharing.organizations.tests.factories import EmailTemplateFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.utils.buchhaltungsbutler import BuchhaltungsButlerError

CLIENT = "re_sharing.agreements.services_collections.buchhaltungsbutler"
RUN_SIZE = 2
NS = {"s": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"}
SEPA_SETTINGS = {
    "SEPA_CREDITOR_ID": "DE98ZZZ09999999999",
    "SEPA_CREDITOR_NAME": "Example Creditor e.V.",
    "SEPA_CREDITOR_IBAN": "DE02120300000000202051",
    "SEPA_CREDITOR_BIC": "BYLADEM1001",
    "SEPA_MANDATE_PREFIX": "RS",
}


def _active(kind, **kwargs):
    agreement = AgreementFactory(kind=kind, status=Agreement.Status.ACTIVE, **kwargs)
    SepaMandateFactory(agreement=agreement)
    return agreement


class BillingPeriodTest(TestCase):
    def test_monthly_periods_from_first_full_month(self):
        agreement = AgreementFactory(start_date=date(2027, 3, 20))

        periods = next_billing_periods(agreement, until=date(2027, 5, 10))

        assert [(p.start, p.end, p.due_date) for p in periods] == [
            (date(2027, 4, 1), date(2027, 4, 30), date(2027, 4, 5)),
            (date(2027, 5, 1), date(2027, 5, 31), date(2027, 5, 5)),
        ]

    def test_monthly_start_on_first_includes_start_month(self):
        agreement = AgreementFactory(start_date=date(2027, 5, 1))

        periods = next_billing_periods(agreement, until=date(2027, 5, 31))

        assert periods[0].start == date(2027, 5, 1)

    def test_yearly_periods_due_on_fixed_date(self):
        agreement = AgreementFactory(
            kind=MembershipKindFactory(), start_date=date(2026, 10, 10)
        )

        periods = next_billing_periods(agreement, until=date(2028, 4, 1))

        assert [(p.start, p.end, p.due_date) for p in periods] == [
            (date(2027, 1, 1), date(2027, 12, 31), date(2027, 3, 15)),
            (date(2028, 1, 1), date(2028, 12, 31), date(2028, 3, 15)),
        ]

    def test_yearly_start_on_first_of_january(self):
        agreement = AgreementFactory(
            kind=MembershipKindFactory(), start_date=date(2028, 1, 1)
        )

        periods = next_billing_periods(agreement, until=date(2028, 3, 31))

        assert periods[0].start == date(2028, 1, 1)

    def test_no_period_after_end_date(self):
        agreement = AgreementFactory(
            start_date=date(2027, 1, 1), end_date=date(2027, 3, 31)
        )

        periods = next_billing_periods(agreement, until=date(2027, 12, 31))

        assert periods[-1].start == date(2027, 3, 1)


@override_settings(PRE_NOTIFICATION_DAYS=14)
class FirstPeriodTest(TestCase):
    def _first(self, kind, start, decided, amount):
        agreement = _active(kind, start_date=start, amount=Decimal(amount))
        return create_first_period_collection(agreement, decided)

    def test_yearly_october_start_two_twelfths(self):
        collection = self._first(
            MembershipKindFactory(), date(2027, 10, 10), date(2027, 10, 12), 60
        )

        assert collection.amount == Decimal("10.00")
        assert collection.period_start == date(2027, 11, 1)
        assert collection.period_end == date(2027, 12, 31)
        assert collection.due_date == date(2027, 10, 26)
        assert collection.status == Collection.Status.NOTIFIED
        assert collection.reference
        assert collection.mandate is not None

    def test_yearly_january_start_due_on_fixed_date(self):
        collection = self._first(
            MembershipKindFactory(), date(2027, 1, 20), date(2027, 2, 1), 60
        )

        assert collection.amount == Decimal("55.00")
        assert collection.period_start == date(2027, 2, 1)
        assert collection.due_date == date(2027, 3, 15)

    def test_yearly_december_start_none(self):
        assert (
            self._first(
                MembershipKindFactory(), date(2027, 12, 3), date(2027, 12, 4), 60
            )
            is None
        )

    def test_yearly_first_of_january_none(self):
        assert (
            self._first(
                MembershipKindFactory(), date(2028, 1, 1), date(2027, 12, 1), 60
            )
            is None
        )

    def test_monthly_mid_month_by_day(self):
        collection = self._first(
            AgreementKindFactory(), date(2027, 3, 20), date(2027, 3, 10), 120
        )

        assert collection.amount == Decimal("46.45")
        assert collection.period_start == date(2027, 3, 20)
        assert collection.period_end == date(2027, 3, 31)
        assert collection.due_date == date(2027, 3, 24)

    def test_monthly_from_start_date_not_decision_date(self):
        collection = self._first(
            AgreementKindFactory(), date(2027, 4, 16), date(2027, 3, 1), 120
        )

        assert collection.amount == Decimal("60.00")
        assert collection.due_date == date(2027, 4, 5)

    def test_monthly_start_on_first_none(self):
        assert (
            self._first(AgreementKindFactory(), date(2027, 5, 1), date(2027, 4, 1), 120)
            is None
        )

    def test_rounding_to_cent(self):
        collection = self._first(
            AgreementKindFactory(), date(2027, 2, 2), date(2027, 1, 1), 100
        )

        assert collection.amount == Decimal("96.43")


@override_settings(COLLECTION_LOOKAHEAD_DAYS=45, SEPA_MANDATE_PREFIX="RS")
class CreateDueCollectionsTest(TestCase):
    def setUp(self):
        self.kind = AgreementKindFactory()

    def test_monthly_collection_within_lookahead(self):
        agreement = _active(self.kind, start_date=date(2027, 1, 1))

        created = create_due_collections(date(2027, 2, 20))

        march = agreement.collections_of_agreement.get(period_start=date(2027, 3, 1))
        assert march.amount == Decimal("120.00")
        assert march.due_date == date(2027, 3, 5)
        assert march.period_end == date(2027, 3, 31)
        assert march.status == Collection.Status.PLANNED
        assert march.mandate == agreement.active_mandate
        assert march.reference == f"RS-C-{march.id:06d}"
        assert march in created

        create_due_collections(date(2027, 2, 20))
        assert (
            agreement.collections_of_agreement.filter(
                period_start=date(2027, 3, 1)
            ).count()
            == 1
        )

    def test_yearly_collection_on_fixed_date(self):
        agreement = _active(
            MembershipKindFactory(), start_date=date(2026, 1, 1), amount=Decimal(60)
        )

        create_due_collections(date(2027, 2, 1))

        collection = agreement.collections_of_agreement.get(
            period_start=date(2027, 1, 1)
        )
        assert collection.amount == Decimal(60)
        assert collection.due_date == date(2027, 3, 15)

    def test_partial_start_period_not_billed(self):
        agreement = _active(self.kind, start_date=date(2027, 3, 20))

        create_due_collections(date(2027, 3, 1))

        assert not agreement.collections_of_agreement.filter(
            period_start__lt=date(2027, 4, 1)
        ).exists()

    def test_amount_frozen(self):
        agreement = _active(self.kind, start_date=date(2027, 1, 1))
        create_due_collections(date(2027, 2, 15))
        agreement.amount = Decimal(150)
        agreement.save()

        create_due_collections(date(2027, 3, 20))

        amounts = dict(
            agreement.collections_of_agreement.values_list("period_start", "amount")
        )
        assert amounts[date(2027, 3, 1)] == Decimal(120)
        assert amounts[date(2027, 4, 1)] == Decimal(150)

    def test_none_after_end_date(self):
        agreement = _active(
            self.kind, start_date=date(2027, 1, 1), end_date=date(2027, 3, 31)
        )

        create_due_collections(date(2027, 4, 1))

        assert not agreement.collections_of_agreement.filter(
            period_start__gt=date(2027, 3, 31)
        ).exists()

    def test_none_for_inactive_kind_or_submitted_agreement(self):
        inactive = _active(
            AgreementKindFactory(is_active=False), start_date=date(2027, 1, 1)
        )
        submitted = AgreementFactory(start_date=date(2027, 1, 1))

        create_due_collections(date(2027, 2, 20))

        assert not inactive.collections_of_agreement.exists()
        assert not submitted.collections_of_agreement.exists()

    def test_cancelled_period_not_recreated(self):
        agreement = _active(self.kind, start_date=date(2027, 1, 1))
        create_due_collections(date(2027, 2, 20))
        agreement.collections_of_agreement.update(status=Collection.Status.CANCELLED)

        create_due_collections(date(2027, 2, 20))

        assert not agreement.collections_of_agreement.exclude(
            status=Collection.Status.CANCELLED
        ).exists()

    def test_periods_due_before_creation_skipped(self):
        agreement = _active(self.kind, start_date=date(2020, 1, 1))
        Agreement.objects.filter(id=agreement.id).update(
            created=timezone.make_aware(datetime(2027, 3, 10))  # noqa: DTZ001
        )

        create_due_collections(date(2027, 3, 10))

        starts = list(
            agreement.collections_of_agreement.values_list("period_start", flat=True)
        )
        assert starts == [date(2027, 4, 1)]


@override_settings(PRE_NOTIFICATION_DAYS=14, **SEPA_SETTINGS)
class NotifyDueCollectionsTest(TestCase):
    def setUp(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.AGREEMENT_PRE_NOTIFICATION,
            subject="Pre-notification",
            body=(
                "{{ collection.amount }} {{ collection.due_date }} "
                "{{ mandate_reference }} {{ creditor_id }}"
            ),
        )

    def test_email_for_each_collection_mode(self):
        collection = CollectionFactory(due_date=date(2027, 3, 5))
        admin = make_admin(collection.agreement.organization)

        with self.captureOnCommitCallbacks(execute=True):
            notify_due_collections(date(2027, 2, 19))

        collection.refresh_from_db()
        assert collection.status == Collection.Status.NOTIFIED
        assert collection.notified_at is not None
        assert mail.outbox[0].to == [admin.email]
        body = mail.outbox[0].body
        assert "120.00" in body
        assert collection.mandate.reference in body
        assert "DE98ZZZ09999999999" in body
        assert VALID_IBAN not in body

    def test_no_email_once_at_approval(self):
        agreement = AgreementFactory(
            kind=MembershipKindFactory(), status=Agreement.Status.ACTIVE
        )
        collection = CollectionFactory(agreement=agreement, due_date=date(2027, 3, 15))

        with self.captureOnCommitCallbacks(execute=True):
            notify_due_collections(date(2027, 3, 1))

        collection.refresh_from_db()
        assert collection.status == Collection.Status.NOTIFIED
        assert len(mail.outbox) == 0

    def test_not_yet_due(self):
        collection = CollectionFactory(due_date=date(2027, 3, 5))

        notify_due_collections(date(2027, 2, 18))

        collection.refresh_from_db()
        assert collection.status == Collection.Status.PLANNED

    def test_first_period_collection_not_picked_up_again(self):
        collection = CollectionFactory(
            due_date=date(2027, 3, 5), status=Collection.Status.NOTIFIED
        )

        with self.captureOnCommitCallbacks(execute=True):
            notified = notify_due_collections(date(2027, 3, 1))

        assert collection not in notified
        assert len(mail.outbox) == 0

    def test_command(self):
        CollectionFactory(due_date=timezone.localdate())
        out = StringIO()

        call_command("create_agreement_collections", stdout=out)

        assert "notified 1" in out.getvalue()


@override_settings(**SEPA_SETTINGS)
class CollectionRunTest(TestCase):
    def setUp(self):
        self.manager = make_manager()
        self.fee = CollectionFactory(
            status=Collection.Status.NOTIFIED, due_date=date(2027, 3, 5)
        )
        self.deposit = CollectionFactory(
            agreement=self.fee.agreement,
            mandate=self.fee.mandate,
            kind=Collection.Kind.DEPOSIT,
            amount=Decimal(360),
            status=Collection.Status.NOTIFIED,
            due_date=date(2027, 3, 1),
        )
        revoked = SepaMandateFactory(revoked_on=date(2027, 2, 1))
        self.without_mandate = CollectionFactory(
            agreement=revoked.agreement,
            mandate=revoked,
            status=Collection.Status.NOTIFIED,
            due_date=date(2027, 3, 5),
        )
        self.later = CollectionFactory(
            status=Collection.Status.NOTIFIED, due_date=date(2027, 3, 20)
        )

    def test_build_run(self):
        run = build_collection_run(self.manager, date(2027, 3, 5))

        assert run.count == RUN_SIZE
        assert run.total_amount == Decimal("480.00")
        assert run.created_by == self.manager
        for collection in (self.fee, self.deposit):
            collection.refresh_from_db()
            assert collection.status == Collection.Status.SUBMITTED
            assert collection.run == run
        for collection in (self.without_mandate, self.later):
            collection.refresh_from_db()
            assert collection.status == Collection.Status.NOTIFIED

    def test_xml_content(self):
        run = build_collection_run(self.manager, date(2027, 3, 5))

        root = ElementTree.fromstring(run.xml_file.read())  # noqa: S314
        transactions = root.findall(".//s:DrctDbtTxInf", NS)
        assert len(transactions) == RUN_SIZE
        assert {t.find("s:PmtId/s:EndToEndId", NS).text for t in transactions} == {
            self.fee.reference,
            self.deposit.reference,
        }
        mandate_ids = {
            t.find("s:DrctDbtTx/s:MndtRltdInf/s:MndtId", NS).text for t in transactions
        }
        assert mandate_ids == {self.fee.mandate.reference}
        signature_dates = {
            t.find("s:DrctDbtTx/s:MndtRltdInf/s:DtOfSgntr", NS).text
            for t in transactions
        }
        assert signature_dates == {"2027-02-01"}
        amounts = {t.find("s:InstdAmt", NS).text for t in transactions}
        assert amounts == {"120.00", "360.00"}
        assert {n.text for n in root.findall(".//s:BtchBookg", NS)} == {"false"}
        assert {n.text for n in root.findall(".//s:SeqTp", NS)} == {"RCUR"}
        assert (
            root.find(".//s:CdtrSchmeId//s:Othr/s:Id", NS).text == "DE98ZZZ09999999999"
        )
        assert root.find(".//s:CdtrAcct//s:IBAN", NS).text == "DE02120300000000202051"

    def test_no_collections_refused(self):
        with pytest.raises(AgreementError):
            build_collection_run(self.manager, date(2027, 1, 1))

    def test_non_manager_denied(self):
        with pytest.raises(PermissionDenied):
            build_collection_run(
                make_admin(self.fee.agreement.organization), date(2027, 3, 5)
            )

    def test_mark_uploaded_and_delete_refused(self):
        run = build_collection_run(self.manager, date(2027, 3, 5))

        mark_run_uploaded(self.manager, run)

        assert run.uploaded_at is not None
        assert run.uploaded_by == self.manager
        with pytest.raises(AgreementError):
            mark_run_uploaded(self.manager, run)
        with pytest.raises(AgreementError):
            delete_collection_run(self.manager, run)

    def test_delete_returns_collections_to_notified(self):
        run = build_collection_run(self.manager, date(2027, 3, 5))

        delete_collection_run(self.manager, run)

        self.fee.refresh_from_db()
        assert self.fee.status == Collection.Status.NOTIFIED
        assert self.fee.run is None
        assert not CollectionRun.objects.exists()


@override_settings(COLLECTION_RETURN_WINDOW_DAYS=7)
class MarkCollectedTest(TestCase):
    def _submitted(self, *, uploaded):
        run = CollectionRunFactory(
            collection_date=date(2027, 3, 5),
            uploaded_at=timezone.now() if uploaded else None,
        )
        return CollectionFactory(status=Collection.Status.SUBMITTED, run=run)

    def test_collected_after_window(self):
        collection = self._submitted(uploaded=True)

        assert mark_collected(date(2027, 3, 13)) == 1

        collection.refresh_from_db()
        assert collection.status == Collection.Status.COLLECTED
        assert collection.collected_at == date(2027, 3, 5)

    def test_inside_window(self):
        collection = self._submitted(uploaded=True)

        mark_collected(date(2027, 3, 8))

        collection.refresh_from_db()
        assert collection.status == Collection.Status.SUBMITTED

    def test_run_never_uploaded(self):
        collection = self._submitted(uploaded=False)

        mark_collected(date(2027, 4, 4))

        collection.refresh_from_db()
        assert collection.status == Collection.Status.SUBMITTED


@override_settings(**SEPA_SETTINGS)
class DetectReturnsTest(TestCase):
    def setUp(self):
        self.collection = CollectionFactory(
            status=Collection.Status.SUBMITTED, amount=Decimal(60)
        )

    def _run(self, rows):
        with patch(f"{CLIENT}.get_transactions", return_value=rows) as mock:
            result = detect_returns(now=timezone.now())
        return result, mock

    def test_match_by_collection_reference(self):
        text = f"RUECKLASTSCHRIFT EREF+{self.collection.reference} MD06"

        result, _ = self._run([{"id": 1, "amount": "-60.00", "purpose": text}])

        self.collection.refresh_from_db()
        assert result["returned"] == 1
        assert self.collection.status == Collection.Status.RETURNED
        assert self.collection.return_text == text

    def test_match_by_mandate_reference_and_amount(self):
        mandate = self.collection.mandate
        rows = [{"id": 2, "amount": "-60", "booking_text": f"MREF+{mandate.reference}"}]

        self._run(rows)

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.RETURNED

    def test_mandate_reference_with_other_amount_does_not_match(self):
        mandate = self.collection.mandate

        self._run([{"id": 3, "amount": "-99", "purpose": f"MREF+{mandate.reference}"}])

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.SUBMITTED
        assert UnmatchedReturn.objects.count() == 1

    def test_return_after_collected(self):
        self.collection.status = Collection.Status.COLLECTED
        self.collection.save()

        self._run(
            [{"id": 4, "amount": "-60", "payment_reference": self.collection.reference}]
        )

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.RETURNED

    def test_reference_prefix_does_not_match_longer_reference(self):
        self._run(
            [{"id": 5, "amount": "-60", "purpose": f"{self.collection.reference}9"}]
        )

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.SUBMITTED

    def test_unmatched_return_listed_once(self):
        rows = [
            {
                "id": 6,
                "amount": "-15",
                "purpose": "Ruecklastschrift unknown",
                "date": "2027-03-08",
            }
        ]

        self._run(rows)
        self._run(rows)

        unmatched = UnmatchedReturn.objects.get()
        assert unmatched.amount == Decimal(-15)
        assert unmatched.booked_on == date(2027, 3, 8)

    def test_positive_and_unrelated_transactions_ignored(self):
        self._run(
            [
                {"id": 7, "amount": "60", "purpose": self.collection.reference},
                {"id": 8, "amount": "-500", "purpose": "Rent for the office"},
                {"id": 9, "amount": "n/a", "purpose": "broken"},
            ]
        )

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.SUBMITTED
        assert not UnmatchedReturn.objects.exists()

    def test_client_error_changes_nothing(self):
        with patch(
            f"{CLIENT}.get_transactions", side_effect=BuchhaltungsButlerError("x")
        ):
            result = detect_returns()

        self.collection.refresh_from_db()
        assert result == {"status": "error"}
        assert self.collection.status == Collection.Status.SUBMITTED
        assert not SyncState.objects.exists()

    def test_last_run_timestamp_stored_and_used(self):
        self._run([])
        state = SyncState.objects.get(key=RETURNS_SYNC_KEY)

        _, mock = self._run([])

        assert mock.call_args.kwargs["date_since_last_modified"] == (
            state.synced_at.strftime("%Y-%m-%d %H:%M:%S")
        )


@override_settings(SEPA_RETURN_FEE=Decimal(5), **SEPA_SETTINGS)
class ReturnInvoiceTest(TestCase):
    def setUp(self):
        EmailTemplateFactory(
            email_type=EmailTemplate.EmailTypeChoices.AGREEMENT_RETURN_INVOICE,
            subject="Invoice",
            body="{{ collection.invoice_number }} {{ collection.invoice_amount }}",
        )
        self.collection = CollectionFactory(
            status=Collection.Status.RETURNED, amount=Decimal(60)
        )
        self.admin = make_admin(self.collection.agreement.organization)
        self.manager = make_manager()

    def test_payload(self):
        payload = build_return_invoice_payload(self.collection)
        organization = self.collection.agreement.organization

        assert payload["item_single_price"] == ["60.00", "5.00"]
        assert payload["due_days"] == "14"
        assert payload["company_name"] == organization.name
        assert payload["street"] == organization.street_and_housenb
        assert payload["city"] == organization.city

    @override_settings(SEPA_RETURN_FEE=Decimal(0))
    def test_payload_without_fee(self):
        assert len(build_return_invoice_payload(self.collection)["item_name"]) == 1

    def test_invoice_returned_collection(self):
        with (
            patch(
                f"{CLIENT}.create_einvoice",
                return_value={"success": True, "invoicenumber": "RE-77"},
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            invoice_returned_collection(self.manager, self.collection)

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.INVOICED
        assert self.collection.invoice_number == "RE-77"
        assert self.collection.invoice_amount == Decimal(65)
        assert mail.outbox[0].to == [self.admin.email]
        assert "RE-77" in mail.outbox[0].body

    def test_client_error_leaves_returned(self):
        with (
            patch(
                f"{CLIENT}.create_einvoice", side_effect=BuchhaltungsButlerError("x")
            ),
            pytest.raises(AgreementError),
        ):
            invoice_returned_collection(self.manager, self.collection)

        self.collection.refresh_from_db()
        assert self.collection.status == Collection.Status.RETURNED
        assert len(mail.outbox) == 0

    def test_not_returned_refused(self):
        self.collection.status = Collection.Status.COLLECTED
        self.collection.save()

        with pytest.raises(AgreementError):
            invoice_returned_collection(self.manager, self.collection)

    def test_out_of_scope_denied(self):
        with pytest.raises(PermissionDenied):
            invoice_returned_collection(
                make_manager(OrganizationGroupFactory()), self.collection
            )

    def test_sync_sets_paid(self):
        self.collection.status = Collection.Status.INVOICED
        self.collection.invoice_number = "RE-77"
        self.collection.save()
        other = CollectionFactory(
            status=Collection.Status.INVOICED, invoice_number="RE-78"
        )
        receipts = [
            {"invoicenumber": "RE-77", "payment_status": "paid"},
            {"invoicenumber": "RE-78", "payment_status": "unpaid"},
        ]

        with patch(f"{CLIENT}.get_receipts", return_value=receipts):
            result = sync_invoice_payments()

        self.collection.refresh_from_db()
        other.refresh_from_db()
        assert result == {"status": "success", "paid": 1}
        assert self.collection.status == Collection.Status.PAID
        assert other.status == Collection.Status.INVOICED

    def test_sync_without_invoices_skips_client(self):
        with patch(f"{CLIENT}.get_receipts") as mock:
            assert sync_invoice_payments()["paid"] == 0
        mock.assert_not_called()

    def test_sync_client_error(self):
        CollectionFactory(status=Collection.Status.INVOICED, invoice_number="RE-1")

        with patch(f"{CLIENT}.get_receipts", side_effect=BuchhaltungsButlerError("x")):
            assert sync_invoice_payments() == {"status": "error"}

    def test_sync_command(self):
        out = StringIO()
        with patch(f"{CLIENT}.get_transactions", return_value=[]):
            call_command("sync_collection_payments", stdout=out)

        assert "Collected 0" in out.getvalue()


class ManualSettlementTest(TestCase):
    def setUp(self):
        self.manager = make_manager()

    def test_deposit_refund_marked_paid(self):
        refund = CollectionFactory(kind=Collection.Kind.DEPOSIT_REFUND, mandate=None)

        mark_collection_paid(self.manager, refund, "Transferred by hand")

        refund.refresh_from_db()
        assert refund.status == Collection.Status.PAID
        assert refund.status_note == "Transferred by hand"
        assert refund.paid_at is not None

    def test_cancel_planned(self):
        collection = CollectionFactory()

        cancel_collection(self.manager, collection, "Waived")

        collection.refresh_from_db()
        assert collection.status == Collection.Status.CANCELLED

    def test_paid_cannot_be_cancelled_or_paid_again(self):
        collection = CollectionFactory(status=Collection.Status.PAID)

        with pytest.raises(AgreementError):
            cancel_collection(self.manager, collection, "x")
        with pytest.raises(AgreementError):
            mark_collection_paid(self.manager, collection, "x")

    def test_admin_denied(self):
        collection = CollectionFactory()

        with pytest.raises(PermissionDenied):
            cancel_collection(
                make_admin(collection.agreement.organization), collection, "x"
            )
