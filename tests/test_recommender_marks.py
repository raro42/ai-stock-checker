"""tradermonty #655/#795: recommender must not invent scores from bool/gap marks."""

from __future__ import annotations

import math

from stock_checker.recommender import RecommendationEngine
from stock_checker.technical_indicators import _finite_signed


def test_finite_signed_refuses_bool_nan():
    assert _finite_signed(1.5)
    assert _finite_signed(-3.0)
    assert _finite_signed(0)
    assert not _finite_signed(True)
    assert not _finite_signed(False)
    assert not _finite_signed(math.nan)
    assert not _finite_signed(None)
    assert not _finite_signed("1.5")


def test_multi_timeframe_score_ignores_bool_change():
    eng = RecommendationEngine()
    # float(True) == 1.0 would invent mild daily up (+5.25)
    assert eng._calculate_multi_timeframe_score({"daily_change": True}) == 0.0
    assert eng._calculate_multi_timeframe_score({"daily_change": 2.0}) == 10.5


def test_technical_score_ignores_bool_rsi_and_marks():
    eng = RecommendationEngine()
    # True→1.0 would look oversold (+12) and True→$1 MA stack invents ±points
    assert eng._calculate_technical_score({"rsi": True}) == 0
    assert (
        eng._calculate_technical_score(
            {"current_price": True, "sma_20": True, "sma_50": True}
        )
        == 0
    )
    assert (
        eng._calculate_technical_score(
            {"current_price": 110.0, "sma_20": 105.0, "sma_50": 100.0}
        )
        == 5
    )
    assert eng._calculate_technical_score({"rsi": 25.0}) == 12
