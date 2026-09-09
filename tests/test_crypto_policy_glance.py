"""Live crypto policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import _crypto_policy_glance_from_portfolio
from openbb_backend.desk import build_crypto_policy_glance


def test_crypto_policy_glance_empty() -> None:
    assert build_crypto_policy_glance(None)["ready"] is False
    assert build_crypto_policy_glance("BTC-USD")["ready"] is False  # type: ignore[arg-type]


def test_crypto_policy_glance_slot_open() -> None:
    g = build_crypto_policy_glance([{"symbol": "AAPL"}, {"symbol": "MSFT"}])
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["slot_open"] is True
    assert g["count"] == 0
    assert g["cap"] == 1
    assert "slot open 0/1" in g["line"]
    assert "BTC/ETH only" in g["line"]
    assert "±10%" in g["line"]


def test_crypto_policy_glance_slot_full() -> None:
    g = build_crypto_policy_glance([{"symbol": "AAPL"}, {"symbol": "BTC-USD"}])
    assert g["ready"] is True
    assert g["tone"] == "full"
    assert g["slot_open"] is False
    assert g["count"] == 1
    assert "slot full 1/1" in g["line"]
    assert "BTC-USD" in g["line"]


def test_crypto_policy_glance_over_cap() -> None:
    g = build_crypto_policy_glance(
        ["BTC-USD", "ETH-USD"],
        max_crypto=1,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["count"] == 2
    assert "over cap 2/1" in g["line"]


def test_crypto_policy_glance_empty_book() -> None:
    g = build_crypto_policy_glance([])
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert "slot open 0/1" in g["line"]


def test_crypto_policy_glance_from_portfolio_dict() -> None:
    g = _crypto_policy_glance_from_portfolio(
        {"holdings": {"AAPL": 1.0, "ETH-USD": 0.5}}
    )
    assert g["ready"] is True
    assert g["tone"] == "full"
    assert g["count"] == 1
    assert "ETH-USD" in g["line"]

