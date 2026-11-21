#!/usr/bin/env python3
"""Tests for AI response parsing (offline)."""

import math

from stock_checker.ai_recommender import AIRecommender, ai_backend_unavailable


def _parser() -> AIRecommender:
    # Avoid constructing Ollama client networking in __init__ path beyond analyzer
    rec = AIRecommender.__new__(AIRecommender)
    return rec


def test_ai_backend_unavailable_detects_ollama_down():
    assert ai_backend_unavailable(
        "Error connecting to Ollama: <urlopen error [Errno 111] Connection refused>\n"
        "Make sure Ollama is running at http://host.docker.internal:11434"
    )
    assert ai_backend_unavailable("Error connecting to cloud LLM at https://x: <urlopen error>")
    assert not ai_backend_unavailable(
        "ACTION: BUY\nCONFIDENCE: HIGH\nSCORE: 40\nREASONING: ok"
    )
    assert not ai_backend_unavailable(
        '{"action":"HOLD","confidence":"LOW","score":0,"reasoning":"wait"}'
    )


def test_trading_prompt_daily_change_refuses_missing_or_bool():
    """tradermonty #798/#655: missing/bool marks → Daily Change n/a (not +0.00)."""
    rec = _parser()
    missing = rec._build_trading_prompt(
        {"symbol": "AAPL", "name": "Apple", "current_price": 100}
    )
    assert "Daily Change: n/a" in missing
    assert "52-Week Position: n/a" in missing
    assert "Current Price: $100.00" in missing
    assert "Previous Close: n/a" in missing

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
    assert "Current Price: n/a" in bool_marks
    assert "Previous Close: n/a" in bool_marks
    assert "52-Week High: n/a" in bool_marks
    assert "52-Week Low: n/a" in bool_marks
    assert "+0.00" not in bool_marks
    assert "$True" not in bool_marks
    assert "True" not in bool_marks

    nan_marks = rec._build_trading_prompt(
        {
            "symbol": "IBM",
            "current_price": math.nan,
            "previous_close": 100.0,
        }
    )
    assert "Daily Change: n/a" in nan_marks
    assert "Current Price: n/a" in nan_marks

    ok = rec._build_trading_prompt(
        {
            "symbol": "AAPL",
            "current_price": 110.0,
            "previous_close": 100.0,
            "52_week_high": 120.0,
            "52_week_low": 80.0,
        }
    )
    assert "Current Price: $110.00" in ok
    assert "Previous Close: $100.00" in ok
    assert "52-Week High: $120.00" in ok
    assert "52-Week Low: $80.00" in ok
    assert "Daily Change: +10.00%" in ok
    assert "52-Week Position: 75.0% of range" in ok


def test_trading_prompt_pe_volume_refuse_bool():
    """tradermonty #700/#655: bool P/E/volume must not invent 1.00 / True prints."""
    rec = _parser()
    bad = rec._build_trading_prompt(
        {
            "symbol": "AAPL",
            "current_price": 100.0,
            "pe_ratio": True,
            "volume": False,
        }
    )
    assert "P/E Ratio:" not in bad
    assert "Volume:" not in bad
    assert "3. P/E ratio" not in bad

    ok = rec._build_trading_prompt(
        {
            "symbol": "AAPL",
            "current_price": 100.0,
            "pe_ratio": 22.5,
            "volume": 2_500_000,
        }
    )
    assert "P/E Ratio: 22.50" in ok
    assert "Volume: 2,500,000" in ok
    assert "3. P/E ratio (valuation)" in ok


def test_bitcoin_prompt_refuses_missing_or_bool():
    """tradermonty #798/#655 + xang1234: never invent flat +0.00 / True→$1 on BTC AI."""
    rec = _parser()
    missing = rec._build_bitcoin_prompt({})
    assert "Current Price: n/a" in missing
    assert "1-Day Change: n/a" in missing
    assert "7-Day Change: n/a" in missing
    assert "30-Day Change: n/a" in missing
    assert "30-Day Volatility: n/a" in missing
    assert "52-Week High: n/a" in missing
    assert "52-Week Low: n/a" in missing
    assert "52-Week Position: n/a" in missing
    assert "+0.00" not in missing

    bool_marks = rec._build_bitcoin_prompt(
        {
            "current_price": True,
            "change_1d": False,
            "change_7d": True,
            "change_30d": False,
            "volatility_30d": True,
            "52_week_high": True,
            "52_week_low": False,
        }
    )
    assert "Current Price: n/a" in bool_marks
    assert "1-Day Change: n/a" in bool_marks
    assert "7-Day Change: n/a" in bool_marks
    assert "30-Day Volatility: n/a" in bool_marks
    assert "52-Week Position: n/a" in bool_marks
    assert "+0.00" not in bool_marks
    assert "$1.00" not in bool_marks

    ok = rec._build_bitcoin_prompt(
        {
            "current_price": 50_000.0,
            "change_1d": 1.5,
            "change_7d": -2.0,
            "change_30d": 4.25,
            "volatility_30d": 3.5,
            "52_week_high": 60_000.0,
            "52_week_low": 40_000.0,
        }
    )
    assert "Current Price: $50,000.00" in ok
    assert "1-Day Change: +1.50%" in ok
    assert "7-Day Change: -2.00%" in ok
    assert "30-Day Change: +4.25%" in ok
    assert "30-Day Volatility: 3.50%" in ok
    assert "52-Week High: $60,000.00" in ok
    assert "52-Week Low: $40,000.00" in ok
    assert "52-Week Position: 50.0% of range" in ok


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


def test_parse_current_price_refuses_bool():
    """tradermonty #700/#655: True mark must not leave parse as usable $1."""
    rec = _parser()
    bad = rec._parse_ai_response(
        '{"action":"HOLD","confidence":"LOW","score":0,"reasoning":"wait"}',
        {"symbol": "AAPL", "current_price": True},
    )
    assert bad["current_price"] is None

    ok = rec._parse_ai_response(
        '{"action":"HOLD","confidence":"LOW","score":0,"reasoning":"wait"}',
        {"symbol": "AAPL", "current_price": 150.5},
    )
    assert ok["current_price"] == 150.5


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
