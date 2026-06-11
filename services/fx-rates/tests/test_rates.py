from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rates import UnknownCurrencyError, quote

client = TestClient(app)


class TestQuoteContract:
    def test_identity_rate_is_one(self) -> None:
        assert quote("USD", "USD") == Decimal("1")

    def test_inverse_rates_are_consistent(self) -> None:
        usd_mxn = quote("USD", "MXN")
        mxn_usd = quote("MXN", "USD")
        # Inverses cross through USD, so round-tripping must stay within
        # the rounding tolerance of the six-decimal contract.
        assert abs(usd_mxn * mxn_usd - Decimal("1")) < Decimal("0.0001")

    def test_six_decimal_contract(self) -> None:
        rate = quote("EUR", "MXN")
        assert -rate.as_tuple().exponent == 6

    def test_case_insensitive_codes(self) -> None:
        assert quote("usd", "mxn") == quote("USD", "MXN")

    def test_unknown_currency_raises(self) -> None:
        with pytest.raises(UnknownCurrencyError):
            quote("USD", "XYZ")

    def test_chf_is_quoted(self) -> None:
        assert quote("USD", "CHF") == Decimal("0.798000")


class TestRatesEndpoint:
    def test_default_base_is_usd(self) -> None:
        response = client.get("/rates")
        assert response.status_code == 200
        body = response.json()
        assert body["base"] == "USD"
        assert "MXN" in body["quotes"]
        assert body["kind"] == "indicative-mid"

    def test_base_is_excluded_from_its_own_quotes(self) -> None:
        body = client.get("/rates", params={"base": "MXN"}).json()
        assert "MXN" not in body["quotes"]

    def test_unknown_base_returns_422_with_supported_list(self) -> None:
        response = client.get("/rates", params={"base": "DOGE"})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "DOGE" in detail["error"]
        assert "USD" in detail["supported"]
