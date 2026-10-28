from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from re_sharing.bookings.tasks import create_draft_invoice
from re_sharing.bookings.tasks import create_einvoice
from re_sharing.bookings.tasks import create_org_draft_invoice
from re_sharing.bookings.tasks import create_org_einvoice
from re_sharing.bookings.tests.factories import BookingFactory
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.utils.buchhaltungsbutler import BuchhaltungsButlerError

CLIENT = "re_sharing.utils.buchhaltungsbutler"
SERVICES = "re_sharing.bookings.services"


def _past_booking(organization):
    past = timezone.now().date() - timedelta(days=10)
    return BookingFactory(
        organization=organization,
        total_amount=Decimal("50.00"),
        start_date=past,
        end_date=past,
    )


@patch(f"{SERVICES}.build_invoice_payload", return_value={})
@patch(f"{SERVICES}.build_einvoice_payload", return_value={})
class BookingInvoiceTasksTest(TestCase):
    def setUp(self):
        self.booking = BookingFactory()

    @patch(f"{CLIENT}.create_draft_invoice", return_value={"success": True})
    def test_draft_success(self, mock_client, *_):
        result = create_draft_invoice.call(self.booking.id)

        assert result == {"booking_id": self.booking.id, "status": "success"}
        mock_client.assert_called_once_with({})

    @patch(f"{CLIENT}.create_draft_invoice", side_effect=BuchhaltungsButlerError("x"))
    def test_draft_error(self, *_):
        result = create_draft_invoice.call(self.booking.id)

        assert result == {"booking_id": self.booking.id, "status": "error"}

    @patch(
        f"{CLIENT}.create_einvoice",
        return_value={"success": True, "invoicenumber": "RE-7"},
    )
    def test_einvoice_success_stores_number(self, *_):
        result = create_einvoice.call(self.booking.id)

        self.booking.refresh_from_db()
        assert result["invoice_number"] == "RE-7"
        assert self.booking.invoice_number == "RE-7"

    @patch(
        f"{CLIENT}.create_einvoice",
        side_effect=BuchhaltungsButlerError("x", api_message="invalid"),
    )
    def test_einvoice_refused_returns_message(self, *_):
        result = create_einvoice.call(self.booking.id)

        assert result == {
            "booking_id": self.booking.id,
            "status": "error",
            "message": "invalid",
        }

    @patch(f"{CLIENT}.create_einvoice", side_effect=BuchhaltungsButlerError("x"))
    def test_einvoice_unreachable(self, *_):
        result = create_einvoice.call(self.booking.id)

        assert result == {"booking_id": self.booking.id, "status": "error"}

    @patch(f"{CLIENT}.create_einvoice", return_value={"message": "odd"})
    def test_einvoice_without_success_flag(self, *_):
        result = create_einvoice.call(self.booking.id)

        assert result["status"] == "error"
        assert result["message"] == "odd"


@patch(f"{SERVICES}.build_org_invoice_payload", return_value={})
@patch(f"{SERVICES}.build_org_einvoice_payload", return_value={})
class OrganizationInvoiceTasksTest(TestCase):
    def setUp(self):
        self.organization = OrganizationFactory()

    def test_no_bookings(self, *_):
        assert create_org_draft_invoice.call(self.organization.id)["status"] == (
            "no_bookings"
        )
        assert create_org_einvoice.call(self.organization.id)["status"] == (
            "no_bookings"
        )

    @patch(f"{CLIENT}.create_draft_invoice", return_value={"success": True})
    def test_draft_success(self, *_):
        _past_booking(self.organization)

        result = create_org_draft_invoice.call(self.organization.id)

        assert result["status"] == "success"
        assert result["booking_count"] == 1

    @patch(f"{CLIENT}.create_draft_invoice", side_effect=BuchhaltungsButlerError("x"))
    def test_draft_error(self, *_):
        _past_booking(self.organization)

        result = create_org_draft_invoice.call(self.organization.id)

        assert result == {"organization_id": self.organization.id, "status": "error"}

    @patch(
        f"{CLIENT}.create_einvoice",
        return_value={"success": True, "invoicenumber": "RE-9"},
    )
    def test_einvoice_success(self, *_):
        booking = _past_booking(self.organization)

        result = create_org_einvoice.call(self.organization.id)

        booking.refresh_from_db()
        assert result["invoice_number"] == "RE-9"
        assert booking.invoice_number == "RE-9"

    @patch(
        f"{CLIENT}.create_einvoice",
        side_effect=BuchhaltungsButlerError("x", api_message="invalid"),
    )
    def test_einvoice_refused(self, *_):
        _past_booking(self.organization)

        result = create_org_einvoice.call(self.organization.id)

        assert result["message"] == "invalid"

    @patch(f"{CLIENT}.create_einvoice", side_effect=BuchhaltungsButlerError("x"))
    def test_einvoice_unreachable(self, *_):
        _past_booking(self.organization)

        result = create_org_einvoice.call(self.organization.id)

        assert result == {"organization_id": self.organization.id, "status": "error"}

    @patch(f"{CLIENT}.create_einvoice", return_value={"message": "odd"})
    def test_einvoice_without_success_flag(self, *_):
        _past_booking(self.organization)

        result = create_org_einvoice.call(self.organization.id)

        assert result["message"] == "odd"
