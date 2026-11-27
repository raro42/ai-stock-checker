"""tradermonty #896/#655: crypto rebalance quote must not invent 52w from 24h."""

from __future__ import annotations

from stock_checker.intelligent_trader import _crypto_recommender_quote_from_binance


def test_crypto_quote_derives_prev_and_daily_from_readable_change() -> None:
    row = _crypto_recommender_quote_from_binance(
        "BTC-USD",
        {
            "change_24h": 10.0,
            "high_24h": 120_000.0,
            "low_24h": 100_000.0,
        },
        price=110_000.0,
    )
    assert row["symbol"] == "BTC-USD"
    assert row["current_price"] == 110_000.0
    assert row["daily_change"] == 10.0
    assert abs(row["previous_close"] - 100_000.0) < 1e-6
    # Day tape must not masquerade as a year range.
    assert row["52_week_high"] is None
    assert row["52_week_low"] is None
    assert row["source"] == "binance"


def test_crypto_quote_refuses_bool_gap_change_and_keeps_52w_none() -> None:
    for junk in (True, False, None, "up", float("nan")):
        row = _crypto_recommender_quote_from_binance(
            "ETH-USD",
            {"change_24h": junk, "high_24h": 4_000.0, "low_24h": 3_000.0},
            price=3_500.0,
        )
        assert row["previous_close"] is None
        assert row["daily_change"] is None
        assert row["52_week_high"] is None
        assert row["52_week_low"] is None


def test_crypto_quote_skips_prev_on_minus_100_change() -> None:
    row = _crypto_recommender_quote_from_binance(
        "BTC-USD",
        {"change_24h": -100.0, "high_24h": 1.0, "low_24h": 0.5},
        price=50.0,
    )
    assert row["daily_change"] == -100.0
    assert row["previous_close"] is None  # denom 0 — no invent


def test_crypto_quote_tolerates_bad_binance_shape() -> None:
    row = _crypto_recommender_quote_from_binance("BTC-USD", None, price=100.0)
    assert row["previous_close"] is None
    assert row["daily_change"] is None
    assert row["52_week_high"] is None
