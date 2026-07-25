#!/usr/bin/env python3
"""Tests for AI response parsing (offline)."""

from stock_checker.ai_recommender import AIRecommender


def _parser() -> AIRecommender:
    # Avoid constructing Ollama client networking in __init__ path beyond analyzer
    rec = AIRecommender.__new__(AIRecommender)
    return rec


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
