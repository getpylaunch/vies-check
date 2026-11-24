# vies-check

Check EU VAT numbers in VIES, the EU's official register, from async Python. It normalizes
and validates the format of numbers from every EU country and Northern Ireland, asks VIES, and
gives one of three answers: valid, invalid, or unavailable.

One dependency (`httpx`), fully typed, Python 3.11 and newer.

## Install

```bash
pip install vies-check
```

## Usage

```python
import asyncio
from vies_check import Status, check_vat


async def main() -> None:
    result = await check_vat("DE", "DE 123 456 789")
    if result.status is Status.VALID:
        print("Valid:", result.name or "(name not shared)")
    elif result.status is Status.INVALID:
        print("Not a valid EU VAT number")
    else:
        print("VIES couldn't check it right now, try again later")


asyncio.run(main())
```

`country` is the ISO code (`"DE"`, `"GR"`; `"EL"` and `"XI"` work too). The number may come
with or without its prefix, spaces, dots or dashes.

## Why three outcomes

VIES doesn't hold the data itself: it relays each question to the register of the country
concerned, and those registers go offline or throttle requests regularly. Then VIES answers
with an error, or even with `"valid": false` plus a `userError` such as `MS_UNAVAILABLE`,
`MS_MAX_CONCURRENT_REQ` or `TIMEOUT`, which says nothing about the number.

Treating that as "invalid" tells a real company its number is wrong. Treating it as "valid"
lets a reverse-charge invoice go out without evidence. So `vies-check` returns
`Status.UNAVAILABLE`: keep the number unconfirmed and ask again later. VIES's error code is in
`result.error`. Numbers with the wrong format are rejected as `INVALID` without asking VIES
(`result.checked_in_vies` is then `False`).

## The result

```python
@dataclass(frozen=True)
class Result:
    status: Status  # VALID, INVALID or UNAVAILABLE
    vat_id: str  # normalized, e.g. "DE123456789"
    name: str = ""  # as registered; empty when the country doesn't share it
    address: str = ""
    request_identifier: str = ""
    checked_in_vies: bool = True
    error: str = ""  # e.g. "MS_UNAVAILABLE"
```

## Proof of the check: request identifier

Send your own EU VAT number with the check, and VIES returns a request identifier, a
reference for that exact check. Some tax offices accept it as proof that you checked a
customer's number before invoicing them without VAT.

```python
from vies_check import Requester, check_vat

me = Requester("DE", "DE 987 654 321")
result = await check_vat("FR", "FR12345678901", requester=me)
print(result.request_identifier)
```

An invalid requester number raises `ValueError` when you create the `Requester`.

## More

- **Your own HTTP client:** `check_vat(..., client=httpx.AsyncClient(...))` reuses
  connections and keeps your proxy settings; the client is left open. Otherwise each call
  opens and closes its own, with `timeout` seconds (default 10).
- **Format only:** `normalize()`, `is_valid_format()` and `prefix_for()` work offline. They
  check the shape each country uses, from the VIES FAQ, not the national checksums.
- **Northern Ireland:** `XI` numbers are supported (9 or 12 digits, `GD` + 3 digits for
  government departments, `HA` + 3 digits for health authorities). VIES covers them for trade
  in goods.
- **Logging:** failed checks are logged as warnings on the `vies_check` logger.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy
```

The tests never touch the network: VIES is replaced with `httpx.MockTransport`.

## License

MIT

---

vies-check is extracted from [getpylaunch](https://getpylaunch.com), a FastAPI starter kit for
paid SaaS, where it handles EU VAT for Stripe billing.

Black Friday: the kit is 60% off until 1 December.
