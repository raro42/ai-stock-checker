"""tradermonty #896/#892: liquidity/pressure miss must not invent fake zeros."""

from __future__ import annotations

import pytest

from stock_checker.market_scanner import (
    finalize_crypto_momentum_score,
    liquidity_deep_fields,
    pressure_deep_fields,
)


def test_liquidity_deep_fields_refuses_invent_dead_book() -> None:
    gap = liquidity_deep_fields(None)
    assert gap["liquidity_score"] is None
    assert gap["spread_pct"] is None
    assert gap["tradeable"] is False

    ok = liquidity_deep_fields(
        {"liquidity_score": 80, "spread_pct": 0.1, "tradeable": True}
    )
    assert ok["liquidity_score"] == 80
    assert ok["spread_pct"] == pytest.approx(0.1)
    assert ok["tradeable"] is True


def test_pressure_deep_fields_refuses_invent_balanced_tape() -> None:
    gap = pressure_deep_fields(None)
    assert gap["buy_ratio"] is None
    assert gap["pressure_score"] is None
    assert gap["buy_volume"] is None
    assert gap["sell_volume"] is None

    ok = pressure_deep_fields(
        {
            "buy_ratio": 0.6,
            "pressure_score": 20,
            "buy_volume": 100.0,
            "sell_volume": 80.0,
        }
    )
    assert ok["buy_ratio"] == pytest.approx(0.6)
    assert ok["pressure_score"] == 20


def test_finalize_skips_liquidity_pressure_gaps() -> None:
    base = finalize_crypto_momentum_score({"score": 10.0})
    gap = finalize_crypto_momentum_score(
        {
            "score": 10.0,
            "liquidity_score": None,
            "pressure_score": None,
        }
    )
    assert gap == pytest.approx(base)

    with_liq = finalize_crypto_momentum_score(
        {"score": 10.0, "liquidity_score": 50.0}
    )
    assert with_liq == pytest.approx(base + 50.0 * 0.2)
