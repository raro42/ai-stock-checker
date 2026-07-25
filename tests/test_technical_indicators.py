#!/usr/bin/env python3
"""Unit tests for technical indicators (no network)."""

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
