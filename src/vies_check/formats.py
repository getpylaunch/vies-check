"""EU VAT number formats, as published in the VIES FAQ (question 11).

Only the shape of the number is checked here, not the national checksum.
"""

import re

# ISO country code -> VAT prefix. Greece's ISO code is GR, but its VAT numbers start with
# EL. XI is Northern Ireland, which VIES checks for trade in goods.
COUNTRY_PREFIXES: dict[str, str] = {
    "AT": "AT", "BE": "BE", "BG": "BG", "CY": "CY", "CZ": "CZ", "DE": "DE", "DK": "DK",
    "EE": "EE", "ES": "ES", "FI": "FI", "FR": "FR", "GR": "EL", "HR": "HR", "HU": "HU",
    "IE": "IE", "IT": "IT", "LT": "LT", "LU": "LU", "LV": "LV", "MT": "MT", "NL": "NL",
    "PL": "PL", "PT": "PT", "RO": "RO", "SE": "SE", "SI": "SI", "SK": "SK", "XI": "XI",
}  # fmt: skip

# Shape of the number after the prefix, per VAT prefix.
FORMATS: dict[str, str] = {
    "AT": r"U\d{8}",
    "BE": r"[01]\d{9}",
    "BG": r"\d{9,10}",
    "CY": r"\d{8}[A-Z]",
    "CZ": r"\d{8,10}",
    "DE": r"\d{9}",
    "DK": r"\d{8}",
    "EE": r"\d{9}",
    "EL": r"\d{9}",
    # The first and last characters may be letters or digits, but not both digits.
    "ES": r"[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z]",
    "FI": r"\d{8}",
    "FR": r"[A-Z0-9]{2}\d{9}",
    "HR": r"\d{11}",
    "HU": r"\d{8}",
    "IE": r"\d[A-Z0-9+*]\d{5}[A-Z]{1,2}",
    "IT": r"\d{11}",
    "LT": r"\d{9}|\d{12}",
    "LU": r"\d{8}",
    "LV": r"\d{11}",
    "MT": r"\d{8}",
    "NL": r"\d{9}B\d{2}",
    "PL": r"\d{10}",
    "PT": r"\d{9}",
    "RO": r"\d{2,10}",
    "SE": r"\d{12}",
    "SI": r"\d{8}",
    "SK": r"\d{10}",
    # 9 digits; 12 digits for branch traders; GD for government departments; HA for
    # health authorities.
    "XI": r"\d{9}|\d{12}|GD\d{3}|HA\d{3}",
}

_SEPARATORS = re.compile(r"[\s.\-/]")


def prefix_for(country: str) -> str | None:
    """The VAT prefix for an ISO country code ("GR" -> "EL"). The prefix itself is
    accepted too ("EL" -> "EL"). None when the country isn't checked by VIES."""
    code = country.strip().upper()
    if code in COUNTRY_PREFIXES:
        return COUNTRY_PREFIXES[code]
    return code if code in FORMATS else None


def normalize(country: str, number: str) -> str:
    """'pl 123-456-78-90' -> 'PL1234567890'. Removes spaces, dots, dashes and slashes,
    uppercases, and adds the country's prefix if it's missing."""
    prefix = prefix_for(country) or country.strip().upper()
    value = _SEPARATORS.sub("", number).upper()
    if not value.startswith(prefix):
        value = prefix + value
    return value


def is_valid_format(vat_id: str) -> bool:
    """True when a normalized VAT ID ('DE123456789') has the shape its country uses."""
    prefix, number = vat_id[:2], vat_id[2:]
    pattern = FORMATS.get(prefix)
    return bool(pattern and re.fullmatch(pattern, number))
