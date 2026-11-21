# Changelog

## 0.1.0

First release.

- `check_vat()`: asks VIES and returns `VALID`, `INVALID` or `UNAVAILABLE`. A `userError` other
  than `VALID` or `INVALID` (for example `MS_UNAVAILABLE` or `TIMEOUT`) counts as unavailable.
- Optional `Requester` (your own VAT number), with VIES's `request_identifier` on the result.
- `normalize()`, `is_valid_format()` and `prefix_for()` for all EU countries and Northern
  Ireland (`XI`), with `EL` for Greece.
- One dependency (`httpx`), fully typed, Python 3.11 to 3.15.
