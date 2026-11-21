"""check_vat() against a fake VIES: no test touches the network."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

import vies_check.client
from vies_check import VIES_URL, Requester, Result, Status, check_vat

Reply = dict[str, Any] | httpx.Response | Exception


def check(
    reply: Reply, country: str = "DE", number: str = "123456789", **kwargs: Any
) -> tuple[Result, list[dict[str, Any]]]:
    """Runs check_vat() with VIES answering `reply`. Returns the result and the request
    bodies VIES received."""
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == VIES_URL
        sent.append(json.loads(request.content))
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, json=reply)

    async def run() -> Result:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await check_vat(country, number, client=client, **kwargs)

    return asyncio.run(run()), sent


# --- The three outcomes ---------------------------------------------------------------


def test_valid_number():
    result, sent = check({"valid": True, "name": "ACME GMBH", "address": "---"})

    assert result.status is Status.VALID and result.is_valid
    assert result.vat_id == "DE123456789"
    assert result.name == "ACME GMBH"
    assert result.address == ""  # "---" means the country doesn't share it
    assert sent == [{"countryCode": "DE", "vatNumber": "123456789"}]


def test_unregistered_number_is_invalid():
    result, _ = check({"valid": False, "name": "---", "address": "---"})

    assert result.status is Status.INVALID
    assert result.checked_in_vies


def test_wrong_format_never_reaches_vies():
    result, sent = check({"valid": True}, number="123")

    assert result.status is Status.INVALID
    assert not result.checked_in_vies
    assert sent == []


def test_country_outside_vies_never_reaches_vies():
    result, sent = check({"valid": True}, country="US", number="123456789")

    assert result.status is Status.INVALID
    assert sent == []


@pytest.mark.parametrize(
    "user_error",
    [
        "MS_UNAVAILABLE",
        "MS_MAX_CONCURRENT_REQ",
        "SERVICE_UNAVAILABLE",
        "TIMEOUT",
        "GLOBAL_MAX_CONCURRENT_REQ",
    ],
)
@pytest.mark.parametrize("action_succeed", [True, None])
def test_busy_register_is_unavailable_not_invalid(user_error, action_succeed):
    """VIES can answer "valid": false with a userError when a national register is down or
    busy. That's not a verdict on the number."""
    reply: dict[str, Any] = {"valid": False, "userError": user_error}
    if action_succeed is not None:
        reply["actionSucceed"] = action_succeed

    result, _ = check(reply)

    assert result.status is Status.UNAVAILABLE
    assert result.error == user_error


@pytest.mark.parametrize("user_error", ["INVALID", None])
def test_user_error_invalid_or_missing_means_invalid(user_error):
    result, _ = check({"valid": False, "userError": user_error, "actionSucceed": True})

    assert result.status is Status.INVALID


def test_vies_error_is_unavailable():
    reply = {"actionSucceed": False, "errorWrappers": [{"error": "MS_UNAVAILABLE"}]}

    result, _ = check(reply)

    assert result.status is Status.UNAVAILABLE
    assert result.error == "MS_UNAVAILABLE"


def test_vies_rejecting_the_input_is_invalid():
    reply = {"actionSucceed": False, "errorWrappers": [{"error": "INVALID_INPUT"}]}

    assert check(reply)[0].status is Status.INVALID


def test_errors_in_a_4xx_body_are_read_too():
    reply = httpx.Response(
        400, json={"actionSucceed": False, "errorWrappers": [{"error": "INVALID_INPUT"}]}
    )

    assert check(reply)[0].status is Status.INVALID


@pytest.mark.parametrize(
    "reply",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.ConnectError("no route"),
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(200, text="<html>maintenance</html>"),
        httpx.Response(200, json=["not", "an", "object"]),
    ],
    ids=["timeout", "connect-error", "http-503", "not-json", "not-an-object"],
)
def test_outages_are_unavailable(reply):
    result, _ = check(reply)

    assert result.status is Status.UNAVAILABLE
    assert result.error


# --- Requester and request identifier ---------------------------------------------------


def test_without_requester_no_requester_fields():
    _, sent = check({"valid": True})

    assert "requesterNumber" not in sent[0]


@pytest.mark.parametrize(
    ("country", "number", "expected"),
    [
        ("de", "DE 987-654-321", ("DE", "987654321")),
        ("DE", "987654321", ("DE", "987654321")),
        ("GR", "987654321", ("EL", "987654321")),
    ],
)
def test_requester_is_sent_without_its_prefix(country, number, expected):
    _, sent = check({"valid": True}, requester=Requester(country, number))

    assert (sent[0]["requesterMemberStateCode"], sent[0]["requesterNumber"]) == expected


def test_request_identifier_is_kept_on_valid_and_invalid_results():
    requester = Requester("DE", "987654321")

    valid, _ = check({"valid": True, "requestIdentifier": "WAPIAAAA1"}, requester=requester)
    invalid, _ = check({"valid": False, "requestIdentifier": "WAPIAAAA2"}, requester=requester)

    assert valid.request_identifier == "WAPIAAAA1"
    assert invalid.request_identifier == "WAPIAAAA2"


def test_requester_with_a_bad_number_is_rejected_up_front():
    with pytest.raises(ValueError):
        Requester("DE", "123")
    with pytest.raises(ValueError):
        Requester("US", "123456789")


# --- Other details ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("number", "sent_number"),
    [("XIGD123", "GD123"), ("123 4567 89", "123456789"), ("XI123456789012", "123456789012")],
)
def test_northern_ireland(number, sent_number):
    _, sent = check({"valid": False}, country="XI", number=number)

    assert sent == [{"countryCode": "XI", "vatNumber": sent_number}]


def test_greece_is_sent_as_el():
    _, sent = check({"valid": True}, country="GR", number="123456789")

    assert sent[0]["countryCode"] == "EL"


def test_without_a_client_one_is_created_and_closed(monkeypatch):
    created: list[httpx.AsyncClient] = []
    real_client: Callable[..., httpx.AsyncClient] = httpx.AsyncClient

    def fake_client(**kwargs: Any) -> httpx.AsyncClient:
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"valid": True}))
        client = real_client(transport=transport, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(vies_check.client.httpx, "AsyncClient", fake_client)

    result = asyncio.run(check_vat("DE", "123456789", timeout=3))

    assert result.status is Status.VALID
    assert len(created) == 1 and created[0].is_closed
    assert created[0].timeout.connect == 3
