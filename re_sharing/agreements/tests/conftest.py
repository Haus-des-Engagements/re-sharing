import pytest


@pytest.fixture(autouse=True)
def _in_memory_storage(settings):
    """Keep uploaded test PDFs and SEPA files out of the media folder."""
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "private": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
