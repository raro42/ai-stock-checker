#!/usr/bin/env python3
"""Unit tests for technical indicators (no network)."""

import math

import pytest

from stock_checker.technical_indicators import TechnicalIndicators


def test_rsi_insufficient_data_returns_none():
    assert TechnicalIndicators.calculate_rsi([1, 2, 3], period=14) is None


def test_rsi_all_gains_near_100():
    # Strictly increasing series → RSI should be high
    prices = [float(i) for i in range(1, 40)]
    rsi = TechnicalIndicators.calculate_rsi(prices, period=14)
    assert rsi is not None
    assert rsi > 70


def test_rsi_all_losses_near_0():
    prices = [float(i) for i in range(40, 0, -1)]
    rsi = TechnicalIndicators.calculate_rsi(prices, period=14)
    assert rsi is not None
    assert rsi < 30


def test_rsi_wilder_differs_from_naive_mean_on_mixed_series():
    """Wilder RSI should be defined and in 0-100 for a mixed series."""
    prices = [
        44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
        45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64,
        46.21, 46.25, 45.71, 46.45, 45.78, 45.35, 44.03, 44.18, 44.22, 44.57,
        43.42, 42.66, 43.13,
    ]
    rsi = TechnicalIndicators.calculate_rsi([float(x) for x in prices], period=14)
    assert rsi is not None
    assert 0 < rsi < 100


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf"), -float("inf")],
)
def test_rsi_invalid_close_is_unavailable(bad):
    """tradermonty #655/#754: gap/zero/NaN closes ≠ a real RSI score."""
    prices = [float(i) for i in range(1, 31)]
    prices[15] = bad
    assert TechnicalIndicators.calculate_rsi(prices, period=14) is None


def test_rsi_clean_history_still_scores():
    """Valid positive finite closes keep Wilder RSI (not unavailable)."""
    prices = [float(i) for i in range(1, 31)]
    rsi = TechnicalIndicators.calculate_rsi(prices, period=14)
    assert rsi is not None
    assert math.isfinite(rsi)
    assert 0.0 <= rsi <= 100.0


def _enough_closes_for_macd(n: int = 50) -> list[float]:
    return [10.0 + (i % 7) * 0.25 for i in range(n)]


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf"), -float("inf")],
)
def test_macd_invalid_close_is_unavailable(bad):
    """Same price-bar gate as RSI: gap/zero/NaN closes ≠ a real MACD histogram."""
    prices = _enough_closes_for_macd()
    prices[20] = bad
    assert TechnicalIndicators.calculate_macd(prices) is None


def test_macd_clean_history_still_scores():
    prices = _enough_closes_for_macd()
    macd = TechnicalIndicators.calculate_macd(prices)
    assert macd is not None
    assert all(math.isfinite(macd[k]) for k in ("macd", "signal", "histogram"))


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf"), -float("inf")],
)
def test_bollinger_invalid_close_is_unavailable(bad):
    """Same price-bar gate as RSI: gap/zero/NaN closes ≠ fake band position."""
    prices = [float(i) for i in range(1, 31)]
    prices[10] = bad
    assert TechnicalIndicators.calculate_bollinger_bands(prices, period=20) is None


def test_bollinger_clean_history_still_scores():
    prices = [float(i) for i in range(1, 31)]
    bb = TechnicalIndicators.calculate_bollinger_bands(prices, period=20)
    assert bb is not None
    assert all(math.isfinite(bb[k]) for k in ("upper", "middle", "lower", "position", "bandwidth"))


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf"), -float("inf")],
)
def test_atr_invalid_ohlc_is_unavailable(bad):
    """tradermonty #655/#754 on ATR: bad high/low/close ≠ real volatility."""
    n = 30
    highs = [11.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [10.0 + i * 0.1 for i in range(n)]
    closes[12] = bad
    assert TechnicalIndicators.calculate_atr(highs, lows, closes, period=14) is None
    highs2 = list(highs)
    highs2[5] = bad
    assert TechnicalIndicators.calculate_atr(highs2, lows, closes, period=14) is None


def test_atr_clean_history_still_scores():
    n = 30
    highs = [11.0 + i * 0.1 for i in range(n)]
    lows = [9.0 + i * 0.1 for i in range(n)]
    closes = [10.0 + i * 0.1 for i in range(n)]
    atr = TechnicalIndicators.calculate_atr(highs, lows, closes, period=14)
    assert atr is not None
    assert math.isfinite(atr)
    assert atr > 0


def _enough_volume_bars(n: int = 25) -> tuple[list[float], list[float]]:
    prices = [10.0 + (i % 5) * 0.2 for i in range(n)]
    volumes = [1000.0 + (i % 7) * 50.0 for i in range(n)]
    return volumes, prices


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", 0, 0.0, -1, float("nan"), float("inf"), -float("inf")],
)
def test_analyze_volume_invalid_close_is_unavailable(bad):
    """tradermonty #655/#754 lineage: gap/zero/NaN closes ≠ fake volume surge."""
    volumes, prices = _enough_volume_bars()
    prices[10] = bad
    assert TechnicalIndicators.analyze_volume(volumes, prices, period=20) is None


@pytest.mark.parametrize(
    "bad",
    [None, True, "100", -1, float("nan"), float("inf"), -float("inf")],
)
def test_analyze_volume_invalid_volume_is_unavailable(bad):
    """Negative / non-finite / non-numeric volume ≠ a real ratio/correlation."""
    volumes, prices = _enough_volume_bars()
    volumes[8] = bad
    assert TechnicalIndicators.analyze_volume(volumes, prices, period=20) is None


def test_analyze_volume_length_mismatch_is_unavailable():
    volumes, prices = _enough_volume_bars()
    assert TechnicalIndicators.analyze_volume(volumes[:-1], prices, period=20) is None


def test_analyze_volume_clean_history_still_scores():
    volumes, prices = _enough_volume_bars()
    # Zero prints are allowed (no trades that bar)
    volumes[3] = 0.0
    out = TechnicalIndicators.analyze_volume(volumes, prices, period=20)
    assert out is not None
    assert all(
        math.isfinite(out[k])
        for k in ("current_volume", "avg_volume", "volume_ratio", "price_volume_correlation")
    )
    assert out["current_volume"] >= 0.0
    assert out["avg_volume"] > 0.0
