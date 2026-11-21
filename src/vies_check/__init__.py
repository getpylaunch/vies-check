"""Check EU VAT numbers in VIES, the EU's official register, from async Python.

result = await check_vat("DE", "DE 123 456 789")
if result.status is Status.VALID: ...
"""

from vies_check.client import VIES_URL, Requester, Result, Status, check_vat, vies_request
from vies_check.formats import COUNTRY_PREFIXES, FORMATS, is_valid_format, normalize, prefix_for

__version__ = "0.1.0"

__all__ = [
    "COUNTRY_PREFIXES",
    "FORMATS",
    "VIES_URL",
    "Requester",
    "Result",
    "Status",
    "check_vat",
    "is_valid_format",
    "normalize",
    "prefix_for",
    "vies_request",
]
