"""Live crypto policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import _crypto_policy_glance_from_portfolio
from openbb_backend.desk import (
    CRYPTO_POLICY_GLANCE_SYMBOLS_CAP,
    _coerce_crypto_policy_name_cap,
    build_crypto_policy_glance,
)


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
    assert g["designed_rr"] == 1.0
    assert "RR 1" in g["line"]


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


def test_crypto_policy_glance_refuses_bool_cap() -> None:
    """tradermonty #700/#655: False→0 invents over-cap; True→1 must not fake default."""
    g = build_crypto_policy_glance(
        ["BTC-USD"],
        max_crypto=False,  # type: ignore[arg-type]
    )
    assert g["ready"] is True
    assert g["cap"] == 1
    assert g["tone"] == "full"
    assert "slot full 1/1" in g["line"]
    g2 = build_crypto_policy_glance(
        ["BTC-USD", "ETH-USD"],
        max_crypto=True,  # type: ignore[arg-type]
    )
    assert g2["ready"] is True
    assert g2["cap"] == 1
    assert g2["tone"] == "warn"
    assert "over cap 2/1" in g2["line"]


def test_crypto_policy_glance_refuses_bool_name_cap() -> None:
    """True→1 must not invent a one-name crypto strip via held[:True]."""
    assert (
        _coerce_crypto_policy_name_cap(True) == CRYPTO_POLICY_GLANCE_SYMBOLS_CAP
    )
    assert (
        _coerce_crypto_policy_name_cap(False) == CRYPTO_POLICY_GLANCE_SYMBOLS_CAP
    )
    assert _coerce_crypto_policy_name_cap(0) == CRYPTO_POLICY_GLANCE_SYMBOLS_CAP
    assert _coerce_crypto_policy_name_cap(None) == CRYPTO_POLICY_GLANCE_SYMBOLS_CAP
    assert _coerce_crypto_policy_name_cap(2) == 2

    cryptos = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "ADA-USD"]
    g_true = build_crypto_policy_glance(cryptos, max_crypto=1, symbols_n=True)
    assert g_true["ready"] is True
    assert g_true["count"] == 5
    assert len(g_true["symbols"]) == CRYPTO_POLICY_GLANCE_SYMBOLS_CAP
    assert g_true["symbols"] == ["BTC-USD", "ETH-USD", "SOL-USD"]
    assert "BTC-USD" in g_true["line"]
    assert "ETH-USD" in g_true["line"]
    assert "SOL-USD" in g_true["line"]
    assert "DOGE-USD" not in g_true["line"]
    assert "ADA-USD" not in g_true["line"]
    assert "over cap 5/1" in g_true["line"]

    g_false = build_crypto_policy_glance(cryptos, max_crypto=1, symbols_n=False)
    assert len(g_false["symbols"]) == CRYPTO_POLICY_GLANCE_SYMBOLS_CAP
    assert g_false["symbols"] == ["BTC-USD", "ETH-USD", "SOL-USD"]
    assert "SOL-USD" in g_false["line"]
    assert "DOGE-USD" not in g_false["line"]

    g_short = build_crypto_policy_glance(cryptos, max_crypto=1, symbols_n=2)
    assert g_short["symbols"] == ["BTC-USD", "ETH-USD"]
    assert "BTC-USD" in g_short["line"]
    assert "ETH-USD" in g_short["line"]
    assert "SOL-USD" not in g_short["line"]
    # Absolute over-cap count still uses full crypto holdings, not the bit cap.
    assert "over cap 5/1" in g_short["line"]


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

