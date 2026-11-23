"""Offline tests for TradingAgents-style multi-role gating."""

from stock_checker.ai_multi_role import (
    _DEFAULT_NOTE_CHARS,
    _DEFAULT_REASONING_CHARS,
    _clip,
    _coerce_clip_chars,
    build_multi_role_prompt,
    consensus_from_multi_role,
    parse_multi_role_response,
)


def test_coerce_clip_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char FinRobot note; False must not wipe."""
    assert _coerce_clip_chars(True, _DEFAULT_NOTE_CHARS) == _DEFAULT_NOTE_CHARS
    assert _coerce_clip_chars(False, _DEFAULT_REASONING_CHARS) == _DEFAULT_REASONING_CHARS
    assert _coerce_clip_chars(0, _DEFAULT_NOTE_CHARS) == _DEFAULT_NOTE_CHARS
    assert _coerce_clip_chars(None, _DEFAULT_NOTE_CHARS) == _DEFAULT_NOTE_CHARS
    assert _coerce_clip_chars(40, _DEFAULT_NOTE_CHARS) == 40


def test_clip_refuses_bool_char_ceiling() -> None:
    """True→1 must not invent ``u``; False must not wipe via s[:0]."""
    note = "uptrend with fee-friendly pullback"
    assert _clip(note, True) == note
    assert _clip(note, False) == note
    assert _clip(note, 0) == note
    assert _clip(note, 8) == "uptrend "


def test_consensus_note_clip_uses_default_ceiling() -> None:
    """Long officer notes truncate at 160; bool ceiling must not invent 1-char."""
    long_note = "x" * 200
    out = consensus_from_multi_role(
        {
            "bull": {"bias": "BUY", "note": long_note},
            "bear": {"bias": "HOLD", "note": long_note},
            "risk": {"ok": True, "note": long_note},
            "action": "BUY",
            "confidence": "HIGH",
            "score": 40,
            "reasoning": "ok",
        },
        "AAPL",
    )
    assert len(out["bull_note"]) == _DEFAULT_NOTE_CHARS
    assert len(out["bear_note"]) == _DEFAULT_NOTE_CHARS
    assert len(out["risk_note"]) == _DEFAULT_NOTE_CHARS
    assert len(out["ai_reasoning"]) <= _DEFAULT_REASONING_CHARS
    # Without refuse, note[:True] would leave a single "x".
    assert out["bull_note"] != "x"


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


def test_consensus_score_refuses_bool():
    """tradermonty #700/#655: True must not invent consensus score 1."""
    out = consensus_from_multi_role(
        {
            "bull": {"bias": "BUY", "note": "up"},
            "bear": {"bias": "HOLD", "note": "ok"},
            "risk": {"ok": True, "note": "fine"},
            "action": "BUY",
            "confidence": "HIGH",
            "score": True,
            "reasoning": "bool score",
        },
        "AAPL",
    )
    assert out["action"] == "BUY"
    assert out["score"] == 0
    assert out["multi_role_gated"] is False


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
        {
            "symbol": "AAPL",
            "name": "Apple",
            "current_price": 110,
            "previous_close": 100,
            "52_week_high": 120,
            "52_week_low": 90,
            "pe_ratio": 25.5,
            "volume": 1_500_000,
        }
    )
    assert "Daily%: +10.00" in text
    assert "Price: 110.00" in text
    assert "PrevClose: 100.00" in text
    assert "52w High/Low: 120.00 / 90.00" in text
    assert "P/E: 25.50" in text
    assert "Volume: 1,500,000" in text


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


def test_multi_role_prompt_money_pe_volume_refuse_bool():
    """tradermonty #700/#655 + FinRobot: raw Price/PE/Volume must not print True→$1."""
    text = build_multi_role_prompt(
        {
            "symbol": "X",
            "current_price": True,
            "previous_close": False,
            "52_week_high": True,
            "52_week_low": False,
            "pe_ratio": True,
            "volume": False,
        }
    )
    assert "Price: n/a" in text
    assert "PrevClose: n/a" in text
    assert "52w High/Low: n/a / n/a" in text
    assert "P/E:" not in text
    assert "Volume:" not in text
    assert "Price: True" not in text
    assert "P/E: True" not in text
