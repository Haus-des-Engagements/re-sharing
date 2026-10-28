import base64
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import requests
from django.test import SimpleTestCase
from django.test import override_settings

from re_sharing.utils import buchhaltungsbutler as client
from re_sharing.utils.buchhaltungsbutler import BuchhaltungsButlerError


def _response(*, ok=True, status=200, json_data=None, json_error=False):
    response = MagicMock()
    response.ok = ok
    response.status_code = status
    response.text = "body"
    if json_error:
        response.json.side_effect = ValueError("no json")
    else:
        response.json.return_value = json_data if json_data is not None else {}
    return response


@override_settings(
    BUCHHALTUNGSBUTLER_API_KEY="key",
    BUCHHALTUNGSBUTLER_API_CLIENT="client",
    BUCHHALTUNGSBUTLER_API_SECRET="secret",  # noqa: S106
    BUCHHALTUNGSBUTLER_BASE_URL="https://bb.example/api",
)
@patch("re_sharing.utils.buchhaltungsbutler.requests.post")
class BuchhaltungsButlerClientTest(SimpleTestCase):
    def test_sends_basic_auth_and_api_key(self, mock_post):
        mock_post.return_value = _response(json_data={"success": True})

        client.create_draft_invoice({"type": "invoice"})

        url = mock_post.call_args.args[0]
        kwargs = mock_post.call_args.kwargs
        expected = base64.b64encode(b"client:secret").decode()
        assert url == "https://bb.example/api/invoices/create/draft"
        assert kwargs["headers"]["Authorization"] == f"Basic {expected}"
        assert kwargs["json"] == {"type": "invoice", "api_key": "key"}
        assert kwargs["timeout"] == client.TIMEOUT_SECONDS

    def test_returns_parsed_json(self, mock_post):
        mock_post.return_value = _response(
            json_data={"success": True, "invoicenumber": "RE-1"}
        )

        data = client.create_einvoice({})

        assert data["invoicenumber"] == "RE-1"
        assert mock_post.call_args.args[0].endswith("/invoices/create/einvoice")

    def test_http_error_raises(self, mock_post):
        mock_post.return_value = _response(ok=False, status=500)

        with pytest.raises(BuchhaltungsButlerError):
            client.create_einvoice({})

    def test_timeout_raises(self, mock_post):
        mock_post.side_effect = requests.Timeout("slow")

        with pytest.raises(BuchhaltungsButlerError):
            client.create_einvoice({})

    def test_success_false_raises(self, mock_post):
        mock_post.return_value = _response(
            json_data={"success": False, "message": "invalid"}
        )

        with pytest.raises(BuchhaltungsButlerError, match="invalid"):
            client.create_einvoice({})

    def test_invalid_json_raises(self, mock_post):
        mock_post.return_value = _response(json_error=True)

        with pytest.raises(BuchhaltungsButlerError):
            client.create_einvoice({})

    def test_get_transactions_pages_until_short_page(self, mock_post):
        full_page = [{"id": i} for i in range(client.PAGE_SIZE)]
        mock_post.side_effect = [
            _response(json_data={"success": True, "data": full_page}),
            _response(json_data={"success": True, "data": [{"id": "last"}]}),
        ]

        rows = client.get_transactions(date_since_last_modified="2027-03-01 00:00:00")

        assert len(rows) == client.PAGE_SIZE + 1
        first, second = (call.kwargs["json"] for call in mock_post.call_args_list)
        assert first["offset"] == 0
        assert second["offset"] == client.PAGE_SIZE
        assert first["date_since_last_modified"] == "2027-03-01 00:00:00"
        assert mock_post.call_args.args[0].endswith("/transactions/get")

    def test_get_transactions_without_filter(self, mock_post):
        mock_post.return_value = _response(json_data={"success": True, "data": []})

        assert client.get_transactions() == []
        assert "date_since_last_modified" not in mock_post.call_args.kwargs["json"]

    def test_get_receipts_lists_outbound(self, mock_post):
        mock_post.return_value = _response(
            json_data={"success": True, "data": [{"invoicenumber": "RE-1"}]}
        )

        rows = client.get_receipts(invoicenumber="RE-1")

        payload = mock_post.call_args.kwargs["json"]
        assert rows == [{"invoicenumber": "RE-1"}]
        assert payload["list_direction"] == "outbound"
        assert payload["invoicenumber"] == "RE-1"
        assert mock_post.call_args.args[0].endswith("/receipts/get")
