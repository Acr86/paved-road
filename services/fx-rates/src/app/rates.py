"""Indicative FX rates.

A deliberately small domain: a static table of indicative mid-market rates,
cross-computed on demand. The point of this service is to exercise the
platform (build, scan, deploy, preview, observe) with something realistic —
not to be a market-data system.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

# Indicative mid rates expressed as 1 USD = x CCY.
_USD_MID: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "MXN": Decimal("18.7340"),
    "EUR": Decimal("0.9210"),
    "GBP": Decimal("0.7890"),
    "CAD": Decimal("1.3620"),
    "CHF": Decimal("0.7980"),
    "BRL": Decimal("5.4310"),
    "JPY": Decimal("151.2400"),
}

_PRECISION = Decimal("0.000001")


class UnknownCurrencyError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"unknown currency code: {code}")


def supported_currencies() -> list[str]:
    return sorted(_USD_MID)


def quote(base: str, counter: str) -> Decimal:
    """Indicative mid rate for one unit of ``base`` in ``counter`` units.

    Crosses through USD with banker's rounding at six decimals — the rounding
    mode is part of the contract, not an implementation detail.
    """
    base_code = base.upper()
    counter_code = counter.upper()
    for code in (base_code, counter_code):
        if code not in _USD_MID:
            raise UnknownCurrencyError(code)
    rate = _USD_MID[counter_code] / _USD_MID[base_code]
    return rate.quantize(_PRECISION, rounding=ROUND_HALF_EVEN)


def all_quotes(base: str) -> dict[str, str]:
    base_code = base.upper()
    if base_code not in _USD_MID:
        raise UnknownCurrencyError(base_code)
    return {
        counter: str(quote(base_code, counter))
        for counter in supported_currencies()
        if counter != base_code
    }
