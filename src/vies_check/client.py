"""Ask VIES, the EU's register of VAT numbers, whether a number is registered.

VIES is free and needs no key, but it only relays the question to each country's
register, and those go offline or get busy regularly. So a check has three outcomes:
valid, invalid, and unavailable ("ask again later").
"""

import enum
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from vies_check.formats import is_valid_format, normalize, prefix_for

logger = logging.getLogger("vies_check")

VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
DEFAULT_TIMEOUT = 10.0

# userError values that are an answer about the number. Anything else (MS_UNAVAILABLE,
# MS_MAX_CONCURRENT_REQ, SERVICE_UNAVAILABLE, TIMEOUT, ...) means a register was busy or
# offline, even when VIES says "valid": false.
_USER_ERRORS_ABOUT_THE_NUMBER = {None, "", "VALID", "INVALID"}
# errorWrappers codes that are about the request itself, not about VIES being down.
_ERRORS_ABOUT_THE_INPUT = {"INVALID_INPUT"}


class Status(enum.StrEnum):
    VALID = "valid"
    INVALID = "invalid"  # wrong format, or VIES says the number isn't registered
    UNAVAILABLE = "unavailable"  # VIES or the national register couldn't answer


@dataclass(frozen=True)
class Requester:
    """Your own EU VAT number. Sent with a check, it makes VIES return a request
    identifier, a reference for that exact check that you can keep as proof."""

    country: str
    vat_number: str

    def __post_init__(self) -> None:
        vat_id = normalize(self.country, self.vat_number)
        if prefix_for(self.country) is None or not is_valid_format(vat_id):
            raise ValueError(f"Not a valid EU VAT number for the requester: {vat_id}")

    @property
    def vat_id(self) -> str:
        return normalize(self.country, self.vat_number)


@dataclass(frozen=True)
class Result:
    status: Status
    vat_id: str  # normalized, with prefix, e.g. "DE123456789"
    name: str = ""  # as registered; empty when the country doesn't share it
    address: str = ""
    request_identifier: str = ""  # only when a Requester was sent
    checked_in_vies: bool = True  # False when the number was rejected offline
    error: str = ""  # VIES's error code, e.g. "MS_UNAVAILABLE", when it gave one

    @property
    def is_valid(self) -> bool:
        return self.status is Status.VALID


def vies_request(prefix: str, number: str, requester: Requester | None = None) -> dict[str, str]:
    """The JSON body for VIES. The requester's number goes without its prefix: with the
    prefix, VIES rejects the request as INVALID_REQUESTER_INFO."""
    body = {"countryCode": prefix, "vatNumber": number}
    if requester is not None:
        vat_id = requester.vat_id
        body["requesterMemberStateCode"] = vat_id[:2]
        body["requesterNumber"] = vat_id[2:]
    return body


async def check_vat(
    country: str,
    number: str,
    *,
    requester: Requester | None = None,
    client: httpx.AsyncClient | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Result:
    """Checks an EU VAT number in VIES.

    `country` is the ISO code ("DE", "GR"; "EL" and "XI" work too) and `number` the VAT
    number, with or without its prefix, spaces or dashes. Pass your own `client` to reuse
    connections or to set proxies; it's left open.
    """
    vat_id = normalize(country, number)
    if prefix_for(country) is None or not is_valid_format(vat_id):
        return Result(Status.INVALID, vat_id, checked_in_vies=False)

    body = vies_request(vat_id[:2], vat_id[2:], requester)
    try:
        answer = await _ask(body, client, timeout)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("VIES request for %s failed: %r", vat_id, exc)
        return Result(Status.UNAVAILABLE, vat_id, error=type(exc).__name__)

    if answer.get("actionSucceed") is False:
        errors = [str(e.get("error", "")) for e in answer.get("errorWrappers") or []]
        error = ",".join(errors)
        logger.warning("VIES could not check %s: %s", vat_id, error)
        if _ERRORS_ABOUT_THE_INPUT.intersection(errors):
            return Result(Status.INVALID, vat_id, error=error)
        return Result(Status.UNAVAILABLE, vat_id, error=error)

    request_identifier = str(answer.get("requestIdentifier") or "")
    if not answer.get("valid"):
        user_error = answer.get("userError")
        if user_error not in _USER_ERRORS_ABOUT_THE_NUMBER:
            logger.warning("VIES could not check %s: %s", vat_id, user_error)
            return Result(
                Status.UNAVAILABLE,
                vat_id,
                request_identifier=request_identifier,
                error=str(user_error),
            )
        return Result(Status.INVALID, vat_id, request_identifier=request_identifier)

    return Result(
        Status.VALID,
        vat_id,
        name=_shared(answer.get("name")),
        address=_shared(answer.get("address")),
        request_identifier=request_identifier,
    )


async def _ask(body: dict[str, str], client: httpx.AsyncClient | None, timeout: float) -> Any:
    if client is None:
        async with httpx.AsyncClient(timeout=timeout) as own_client:
            return await _post(own_client, body, timeout)
    return await _post(client, body, timeout)


async def _post(client: httpx.AsyncClient, body: dict[str, str], timeout: float) -> Any:
    response = await client.post(VIES_URL, json=body, timeout=timeout)
    if response.is_error:
        # VIES describes request errors in the body; anything else is an outage.
        try:
            answer = response.json()
        except ValueError:
            answer = None
        if isinstance(answer, dict) and answer.get("errorWrappers"):
            return answer
        response.raise_for_status()
    answer = response.json()
    if not isinstance(answer, dict):
        raise ValueError("VIES returned something other than a JSON object")
    return answer


def _shared(value: object) -> str:
    """VIES uses "---" when a country doesn't share the name or address."""
    return str(value or "").replace("---", "").strip()
