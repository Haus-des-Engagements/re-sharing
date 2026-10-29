from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

BOOTSTRAP_VERSION = "v5.3.8"


@pytest.mark.parametrize(
    "static_path",
    [
        "css/bootstrap/bootstrap.min.css",
        "js/vendors/bootstrap/bootstrap.bundle.min.js",
    ],
)
def test_vendored_bootstrap_has_expected_version(static_path):
    file_path = finders.find(static_path)
    assert file_path, f"{static_path} not found in static files"

    header = Path(file_path).read_text(encoding="utf-8")[:300]

    assert BOOTSTRAP_VERSION in header


@pytest.mark.parametrize(
    "url_name",
    ["home", "bookings:list-bookings-webview"],
)
def test_pages_load_minified_bootstrap(client, db, url_name):
    response = client.get(reverse(url_name))
    html = response.content.decode()

    assert "bootstrap.min.css" in html
    assert "bootstrap.bundle.min.js" in html
    assert "bootstrap.bundle.js" not in html
