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
    # float(True) == 1.0 would invent mild daily up (+5.25); bool-only → None
    assert eng._calculate_multi_timeframe_score({"daily_change": True}) is None
    assert eng._calculate_multi_timeframe_score({"daily_change": 2.0}) == 10.5
    # Real flat 0% is readable and contributes 0 — not unavailable.
    assert eng._calculate_multi_timeframe_score({"daily_change": 0.0}) == 0.0


def test_technical_score_ignores_bool_rsi_and_marks():
    eng = RecommendationEngine()
    # True→1.0 would look oversold (+12) and True→$1 MA stack invents ±points
    assert eng._calculate_technical_score({"rsi": True}) is None
    assert (
        eng._calculate_technical_score(
            {"current_price": True, "sma_20": True, "sma_50": True}
        )
        is None
    )
    assert (
        eng._calculate_technical_score(
            {"current_price": 110.0, "sma_20": 105.0, "sma_50": 100.0}
        )
        == 5
    )
    assert eng._calculate_technical_score({"rsi": 25.0}) == 12


def test_bitcoin_recommendation_ignores_bool_pct_and_rsi():
    eng = RecommendationEngine()
    # float(True)==1.0 would invent mild +0.5d momentum (+8); bool-only → unavailable
    bad = eng.analyze_bitcoin_recommendation(
        {"daily_change": True, "weekly_change": False, "rsi": True, "volume_ratio": True}
    )
    assert bad["score"] is None
    assert bad["action"] == "unavailable"
    good = eng.analyze_bitcoin_recommendation({"daily_change": 3.0})
    assert good["score"] == 12
    assert good["action"] == "BUY"


def test_empty_recommender_refuses_invented_hold():
    """Empty quote bag must not invent calm HOLD / score=0 (generate_signals parity)."""
    eng = RecommendationEngine()
    stock = eng.analyze_stock_recommendation({})
    assert stock["score"] is None
    assert stock["action"] == "unavailable"
    btc = eng.analyze_bitcoin_recommendation({})
    assert btc["score"] is None
    assert btc["action"] == "unavailable"


def test_volume_sentiment_score_ignores_bool_soft_factors():
    """False→0 volume / True→1d earnings / True sentiment must not invent soft points."""
    eng = RecommendationEngine()
    # False→0.0 would hit volume_ratio < 0.7 (−3); True→1.0 would hit 0≤d≤2 (−4)
    # and clamp sentiment to +1 (+3 news / +2 OpenBB). Bool-only → None.
    assert (
        eng._calculate_volume_sentiment_score(
            {
                "volume_ratio": False,
                "news_sentiment": True,
                "openbb_sentiment": True,
                "days_to_earnings": True,
            }
        )
        is None
    )
    assert eng._calculate_volume_sentiment_score({"volume_ratio": 2.0}) == 5.0
    assert eng._calculate_volume_sentiment_score({"volume_ratio": 0.5}) == -3.0
    assert eng._calculate_volume_sentiment_score({"news_sentiment": 1.0}) == 3.0
    assert eng._calculate_volume_sentiment_score({"openbb_sentiment": -1.0}) == -2.0
    assert eng._calculate_volume_sentiment_score({"days_to_earnings": 1.0}) == -4.0
    assert eng._calculate_volume_sentiment_score({"days_to_earnings": -0.5}) == -2.0
