from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class TestExtendBookingSeriesCommand(TestCase):
    @patch(
        "re_sharing.bookings.management.commands.extend_booking_series.extend_booking_series"
    )
    def test_command_calls_extend_booking_series(self, mock_extend):
        """Test that command calls the extend_booking_series function"""
        mock_extend.return_value = ["booking1", "booking2"]
        out = StringIO()

        call_command("extend_booking_series", stdout=out)

        mock_extend.assert_called_once()
        assert "Created bookings: ['booking1', 'booking2']" in out.getvalue()

    @patch(
        "re_sharing.bookings.management.commands.extend_booking_series.extend_booking_series"
    )
    def test_command_with_no_bookings_created(self, mock_extend):
        """Test command output when no bookings are created"""
        mock_extend.return_value = []
        out = StringIO()

        call_command("extend_booking_series", stdout=out)

        mock_extend.assert_called_once()
        assert "Created bookings: []" in out.getvalue()
