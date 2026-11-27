"""Binance breakout must not invent flat 0% surge on a zero-volume reference."""

from __future__ import annotations

import pytest

from stock_checker.binance_fetcher import (
    BinanceFetcher,
    _breakout_volume_surge_pct,
)


def test_breakout_volume_surge_refuses_zero_mean_window() -> None:
    # tradermonty #896/#892 + analyze_volume parity: all-zero prior ≠ normal 0%.
    assert _breakout_volume_surge_pct(100.0, [0.0, 0.0, 0.0]) is None
    assert _breakout_volume_surge_pct(0.0, [0.0, 0.0]) is None
    assert _breakout_volume_surge_pct(50.0, []) is None
    assert _breakout_volume_surge_pct(True, [10.0, 10.0]) is None
    assert _breakout_volume_surge_pct(20.0, [10.0, True]) is None


def test_breakout_volume_surge_computes_when_reference_ok() -> None:
    # mean prior = 10 → current 20 = +100%
    assert _breakout_volume_surge_pct(20.0, [10.0, 10.0]) == pytest.approx(100.0)
    # real flat day still speaks 0 when mean > 0
    assert _breakout_volume_surge_pct(10.0, [10.0, 10.0]) == pytest.approx(0.0)


def test_analyze_breakout_skips_volume_bonus_on_zero_window(monkeypatch) -> None:
    fetcher = BinanceFetcher()

    # 6 zero-vol prior days + current with readable OHLC / volume print
    zero_priors = [
        {
            "open_time": i,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 0.0,
            "close_time": i,
        }
        for i in range(6)
    ]
    current = {
        "open_time": 6,
        "open": 1.0,
        "high": 2.0,  # higher high → +40
        "low": 0.9,
        "close": 1.5,  # bullish → +15
        "volume": 100.0,
        "close_time": 6,
    }
    monkeypatch.setattr(
        fetcher, "get_klines", lambda *a, **k: [*zero_priors, current]
    )
    out = fetcher.analyze_breakout("BTCUSDT")
    assert out is not None
    assert out["volume_surge_pct"] is None
    # higher-high 40 + bullish 15; volume bonuses must stay out
    assert out["breakout_score"] == 55
    assert out["is_higher_high"] is True


def test_analyze_breakout_speaks_surge_when_prior_has_volume(monkeypatch) -> None:
    fetcher = BinanceFetcher()
    priors = [
        {
            "open_time": i,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 10.0,
            "close_time": i,
        }
        for i in range(6)
    ]
    current = {
        "open_time": 6,
        "open": 1.0,
        "high": 1.05,
        "low": 0.95,
        "close": 0.99,  # bearish candle
        "volume": 25.0,  # +150% surge → +30 +15
        "close_time": 6,
    }
    monkeypatch.setattr(fetcher, "get_klines", lambda *a, **k: [*priors, current])
    out = fetcher.analyze_breakout("ETHUSDT")
    assert out is not None
    assert out["volume_surge_pct"] == pytest.approx(150.0)
    assert out["breakout_score"] == 45  # volume only (no HH, not bullish)
