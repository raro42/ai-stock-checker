"""Offline tests for TradingAgents-style multi-role gating."""

from stock_checker.ai_multi_role import (
    build_multi_role_prompt,
    consensus_from_multi_role,
    parse_multi_role_response,
)


def test_risk_veto_forces_hold():
    out = consensus_from_multi_role(
        {
            "bull": {"bias": "BUY", "note": "up"},
            "bear": {"bias": "HOLD", "note": "ok"},
            "risk": {"ok": False, "note": "earnings"},
            "action": "BUY",
            "confidence": "HIGH",
            "score": 50,
            "reasoning": "should be vetoed",
        },
        "AAPL",
    )
    assert out["action"] == "HOLD"
    assert out["multi_role_gated"] is True
    assert out["risk_ok"] is False
    assert out["bull_note"] == "up"
    assert "earnings" in out["risk_note"]
    assert out["reasoning"].startswith("Risk veto")


def test_bull_bear_disagreement_hold():
    out = consensus_from_multi_role(
        {
            "bull": {"bias": "BUY", "note": "moon"},
            "bear": {"bias": "SELL", "note": "dump"},
            "risk": {"ok": True, "note": "fine"},
            "action": "BUY",
            "confidence": "HIGH",
            "score": 40,
            "reasoning": "conflict",
        },
        "NVDA",
    )
    assert out["action"] == "HOLD"
    assert out["confidence"] == "MEDIUM"


def test_parse_multi_role_json():
    raw = """```json
{"bull":{"bias":"HOLD","note":"meh"},"bear":{"bias":"HOLD","note":"meh"},
"risk":{"ok":true,"note":"ok"},"action":"HOLD","confidence":"LOW","score":0,"reasoning":"flat"}
```"""
    out = parse_multi_role_response(raw, {"symbol": "WMT"})
    assert out is not None
    assert out["parse_mode"] == "multi_role"
    assert out["action"] == "HOLD"


def test_multi_role_prompt_daily_pct_healthy():
    text = build_multi_role_prompt(
        {"symbol": "AAPL", "name": "Apple", "current_price": 110, "previous_close": 100}
    )
    assert "Daily%: +10.00" in text


def test_multi_role_prompt_daily_pct_unavailable_on_bool_or_missing():
    """tradermonty #798: bool/missing marks speak n/a — never invent flat +0.00."""
    for data in (
        {"symbol": "X", "current_price": True, "previous_close": 100},
        {"symbol": "X", "current_price": 100, "previous_close": True},
        {"symbol": "X", "current_price": None, "previous_close": 100},
        {"symbol": "X"},
    ):
        text = build_multi_role_prompt(data)
        assert "Daily%: n/a" in text
        assert "Daily%: +0.00" not in text
