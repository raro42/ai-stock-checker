#!/usr/bin/env python3
"""Tests for AI response parsing (offline)."""

import math

from stock_checker.ai_recommender import AIRecommender


def _parser() -> AIRecommender:
    # Avoid constructing Ollama client networking in __init__ path beyond analyzer
    rec = AIRecommender.__new__(AIRecommender)
    return rec


def test_trading_prompt_daily_change_refuses_missing_or_bool():
    """tradermonty #798/#655: missing/bool marks → Daily Change n/a (not +0.00)."""
    rec = _parser()
    missing = rec._build_trading_prompt(
        {"symbol": "AAPL", "name": "Apple", "current_price": 100}
    )
    assert "Daily Change: n/a" in missing
    assert "52-Week Position: n/a" in missing

    bool_marks = rec._build_trading_prompt(
        {
            "symbol": "MSFT",
            "current_price": True,
            "previous_close": False,
            "52_week_high": True,
            "52_week_low": False,
        }
    )
    assert "Daily Change: n/a" in bool_marks
    assert "52-Week Position: n/a" in bool_marks
    assert "+0.00" not in bool_marks

    nan_marks = rec._build_trading_prompt(
        {
            "symbol": "IBM",
            "current_price": math.nan,
            "previous_close": 100.0,
        }
    )
    assert "Daily Change: n/a" in nan_marks

    ok = rec._build_trading_prompt(
        {
            "symbol": "AAPL",
            "current_price": 110.0,
            "previous_close": 100.0,
            "52_week_high": 120.0,
            "52_week_low": 80.0,
        }
    )
    assert "Daily Change: +10.00%" in ok
    assert "52-Week Position: 75.0% of range" in ok


def test_parse_json_response():
    rec = _parser()
    out = rec._parse_ai_response(
        '{"action":"BUY","confidence":"HIGH","score":42,"reasoning":"Momentum up"}',
        {"symbol": "AAPL", "current_price": 100},
    )
    assert out["action"] == "BUY"
    assert out["confidence"] == "HIGH"
    assert out["score"] == 42
    assert out["parse_mode"] == "json"


def test_parse_json_score_refuses_bool():
    """tradermonty #700/#655: True must not invent score 1."""
    rec = _parser()
    out = rec._parse_ai_response(
        '{"action":"BUY","confidence":"HIGH","score":true,"reasoning":"bad"}',
        {"symbol": "AAPL"},
    )
    assert out["parse_mode"] == "json"
    assert out["score"] == 0
    assert out["action"] == "BUY"


def test_parse_text_response():
    rec = _parser()
    text = "ACTION: SELL\nCONFIDENCE: MEDIUM\nSCORE: -20\nREASONING: Extended rally"
    out = rec._parse_ai_response(text, {"symbol": "TSLA"})
    assert out["action"] == "SELL"
    assert out["confidence"] == "MEDIUM"
    assert out["score"] == -20
    assert out["parse_mode"] == "text"


def test_reject_unstructured_response():
    rec = _parser()
    out = rec._parse_ai_response("I think maybe buy? looks ok", {"symbol": "MSFT"})
    assert out["action"] == "HOLD"
    assert out["confidence"] == "LOW"
    assert out["parse_mode"] == "rejected"
