"""IBAN normalisation and checksum validation (ISO 13616, mod 97)."""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

IBAN_PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
IBAN_CHECKSUM_REMAINDER = 1
IBAN_MODULUS = 97


def normalize_iban(value: str) -> str:
    return re.sub(r"\s+", "", value or "").upper()


def iban_checksum_ok(iban: str) -> bool:
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(char, 36)) for char in rearranged)
    return int(digits) % IBAN_MODULUS == IBAN_CHECKSUM_REMAINDER


def validate_iban(value: str) -> None:
    iban = normalize_iban(value)
    if not IBAN_PATTERN.match(iban) or not iban_checksum_ok(iban):
        raise ValidationError(_("This is not a valid IBAN."), code="invalid_iban")
