import pytest

from vies_check import COUNTRY_PREFIXES, FORMATS, is_valid_format, normalize, prefix_for


def test_normalize_removes_separators_and_adds_the_prefix():
    assert normalize("DE", "de 123.456-789") == "DE123456789"
    assert normalize("DE", "123456789") == "DE123456789"
    assert normalize("pl", "123/456/78/90") == "PL1234567890"


def test_greece_uses_el():
    assert prefix_for("GR") == "EL"
    assert prefix_for("EL") == "EL"
    assert normalize("GR", "123456789") == "EL123456789"
    assert normalize("EL", "EL 123 456 789") == "EL123456789"


def test_countries_outside_vies():
    assert prefix_for("US") is None
    assert prefix_for("GB") is None  # only Northern Ireland (XI) is in VIES
    assert prefix_for("XI") == "XI"


def test_every_country_has_a_format():
    assert set(COUNTRY_PREFIXES.values()) == set(FORMATS)
    assert len(COUNTRY_PREFIXES) == 28  # the 27 EU countries and Northern Ireland


# One valid shape per country, following the VIES FAQ (question 11).
@pytest.mark.parametrize(
    "vat_id",
    [
        "ATU12345678",
        "BE0123456789",
        "BE1123456789",
        "BG123456789",
        "BG1234567890",
        "CY12345678L",
        "CZ12345678",
        "CZ1234567890",
        "DE123456789",
        "DK12345678",
        "EE123456789",
        "EL123456789",
        "ESX1234567X",
        "ESX12345678",
        "ES12345678X",
        "FI12345678",
        "FRXX123456789",
        "FR12123456789",
        "HR12345678901",
        "HU12345678",
        "IE1S12345L",
        "IE1234567WI",
        "IT12345678901",
        "LT123456789",
        "LT123456789012",
        "LU12345678",
        "LV12345678901",
        "MT12345678",
        "NL123456789B01",
        "PL1234567890",
        "PT123456789",
        "RO12",
        "RO1234567890",
        "SE123456789012",
        "SI12345678",
        "SK1234567890",
        "XI123456789",
        "XI123456789012",
        "XIGD123",
        "XIHA567",
    ],
)
def test_valid_formats(vat_id):
    assert is_valid_format(vat_id), vat_id


@pytest.mark.parametrize(
    "vat_id",
    [
        "AT12345678",  # AT always has a U after the prefix
        "BE2123456789",  # BE starts with 0 or 1
        "DE12345678",  # too short
        "ES123456789",  # first and last can't both be digits
        "EL12345678",
        "GR123456789",  # Greece's prefix is EL, not GR
        "NL123456789A01",
        "PL123456789",
        "RO1",
        "XI12345678",  # 8 digits
        "XI1234567890",  # 10 digits
        "XIGD1234",
        "XIHA99",
        "XIAB123",
        "US123456789",
        "",
    ],
)
def test_invalid_formats(vat_id):
    assert not is_valid_format(vat_id), vat_id
