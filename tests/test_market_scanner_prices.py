"""tradermonty #655/#754/#798: scan marks/% refuse bool/gap/NaN invent."""

from __future__ import annotations

import math

import pytest

from stock_checker.market_scanner import (
    breakout_from_high,
    coerce_scan_price,
    coerce_signed_pct,
    day_range_pct,
    finalize_crypto_momentum_score,
    rank_crypto_from_ticker,
    stock_pulse_side,
)


def test_coerce_scan_price_refuses_invalid():
    assert coerce_scan_price(100.5) == 100.5
    assert coerce_scan_price(True) is None
    assert coerce_scan_price(False) is None
    assert coerce_scan_price(0) is None
    assert coerce_scan_price(-1) is None
    assert coerce_scan_price(math.nan) is None
    assert coerce_scan_price(None) is None
    assert coerce_scan_price("12.5") is None


def test_coerce_signed_pct_refuses_invalid_and_keeps_signed():
    assert coerce_signed_pct(-1.5) == -1.5
    assert coerce_signed_pct(0.0) == 0.0
    assert coerce_signed_pct(2.25) == 2.25
    assert coerce_signed_pct(True) is None
    assert coerce_signed_pct(False) is None
    assert coerce_signed_pct(math.nan) is None
    assert coerce_signed_pct(None) is None
    assert coerce_signed_pct("1.2") is None


def test_stock_pulse_side_refuses_invalid_no_invent_flat():
    """xang1234 breadth: unavailable % must not count as flat in stock_scan_n."""
    assert stock_pulse_side(1.5) == "up"
    assert stock_pulse_side(-0.25) == "down"
    assert stock_pulse_side(0.0) == "flat"
    assert stock_pulse_side(True) is None
    assert stock_pulse_side(False) is None
    assert stock_pulse_side(math.nan) is None
    assert stock_pulse_side(None) is None
    assert stock_pulse_side("1.2") is None


def test_breakout_from_high_refuses_bool_and_gap():
    assert breakout_from_high(95.0, 100.0) == (95.0, 100.0, -5.0)
    assert breakout_from_high(True, 100.0) is None
    assert breakout_from_high(95.0, True) is None
    assert breakout_from_high(0, 100.0) is None
    assert breakout_from_high(95.0, math.nan) is None
    assert breakout_from_high(95.0, None) is None


def test_day_range_pct_refuses_invalid_no_invent_flat():
    """Missing high/low must not invent 0% vol via last-print fallback."""
    assert day_range_pct(110.0, 100.0) == 10.0
    assert day_range_pct(100.0, 100.0) == 0.0  # real flat day
    assert day_range_pct(True, 100.0) is None
    assert day_range_pct(110.0, True) is None
    assert day_range_pct(None, 100.0) is None
    assert day_range_pct(110.0, None) is None
    assert day_range_pct(math.nan, 100.0) is None
    assert day_range_pct(90.0, 100.0) is None  # inverted
    assert day_range_pct(0, 100.0) is None
    assert day_range_pct(110.0, 0) is None


def test_rank_crypto_from_ticker_refuses_incomplete_marks():
    """Full-universe momentum must not invent scores from None/bool fields."""
    ok = rank_crypto_from_ticker(
        yf_symbol="BTC-USD",
        binance_symbol="BTCUSDT",
        data={
            "current_price": 50_000.0,
            "change_24h": 2.5,
            "high_24h": 51_000.0,
            "low_24h": 49_000.0,
            "volume_24h": 100.0,
            "volume_usdt": 20_000_000.0,
        },
    )
    assert ok is not None
    assert ok["symbol"] == "BTC-USD"
    assert ok["price"] == 50_000.0
    assert ok["change_24h"] == 2.5
    assert ok["volatility"] == pytest.approx((51_000.0 - 49_000.0) / 49_000.0 * 100.0)
    assert ok["score"] > 2.5

    # Missing 24h% after ticker coerce — do not invent flat momentum.
    assert (
        rank_crypto_from_ticker(
            yf_symbol="ETH-USD",
            binance_symbol="ETHUSDT",
            data={
                "current_price": 3_000.0,
                "change_24h": None,
                "high_24h": 3_100.0,
                "low_24h": 2_900.0,
                "volume_usdt": 30_000_000.0,
            },
        )
        is None
    )
    # Bool leftover must not invent $1 / +1% / flat range.
    assert (
        rank_crypto_from_ticker(
            yf_symbol="X-USD",
            binance_symbol="XUSDT",
            data={
                "current_price": True,
                "change_24h": True,
                "high_24h": True,
                "low_24h": True,
                "volume_usdt": True,
            },
        )
        is None
    )
    # volume_usdt=None with present key must not fall through to invent;
    # usable base×price still ranks.
    base_only = rank_crypto_from_ticker(
        yf_symbol="SOL-USD",
        binance_symbol="SOLUSDT",
        data={
            "current_price": 100.0,
            "change_24h": -1.0,
            "high_24h": 105.0,
            "low_24h": 95.0,
            "volume_24h": 200_000.0,
            "volume_usdt": None,
        },
    )
    assert base_only is not None
    assert base_only["volume_usdt"] == pytest.approx(20_000_000.0)
    assert (
        rank_crypto_from_ticker(
            yf_symbol="BAD-USD",
            binance_symbol="BADUSDT",
            data={
                "current_price": 10.0,
                "change_24h": 1.0,
                "high_24h": 11.0,
                "low_24h": 9.0,
                "volume_24h": None,
                "volume_usdt": None,
            },
        )
        is None
    )


def test_finalize_crypto_momentum_score_refuses_bool_bonuses():
    """Deep-analysis True must not invent breakout/RSI/MACD/pressure bonuses."""
    base_only = finalize_crypto_momentum_score({"score": 10.0})
    assert base_only == pytest.approx(10.0)

    ok = finalize_crypto_momentum_score(
        {
            "score": 10.0,
            "breakout_score": 100.0,
            "liquidity_score": 50.0,
            "rsi": 35.0,
            "macd": {"histogram": 0.5},
            "pressure_score": 40.0,
        }
    )
    # 10 + 100*0.3 + 50*0.2 + RSI+5 + MACD+3 + pressure+3
    assert ok == pytest.approx(10.0 + 30.0 + 10.0 + 5 + 3 + 3)

    # Bool leftovers: True*0.3 / True<40 / True>0.1 must not invent bonuses.
    refuse = finalize_crypto_momentum_score(
        {
            "score": 10.0,
            "breakout_score": True,
            "liquidity_score": True,
            "rsi": True,
            "macd": {"histogram": True},
            "pressure_score": True,
        }
    )
    assert refuse == pytest.approx(10.0)

    # Bool base score also refused (fail-open 0).
    assert finalize_crypto_momentum_score({"score": True}) == pytest.approx(0.0)
    assert finalize_crypto_momentum_score({}) == pytest.approx(0.0)
