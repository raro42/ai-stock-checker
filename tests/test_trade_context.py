from stock_checker.trade_context import (
    NOTE_MAX,
    _clip,
    _coerce_note_clip_chars,
    buy_note_from_opportunity,
)


def test_coerce_note_clip_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Book note; False must not wipe."""
    assert _coerce_note_clip_chars(True) == NOTE_MAX
    assert _coerce_note_clip_chars(False) == NOTE_MAX
    assert _coerce_note_clip_chars(0) == NOTE_MAX
    assert _coerce_note_clip_chars(None) == NOTE_MAX
    assert _coerce_note_clip_chars(40) == 40


def test_clip_refuses_bool_char_ceiling() -> None:
    """True→1 must not invent ``T…``; False must not wipe via s[:-1]."""
    note = "Trend template breakout near high"
    assert _clip(note, True) == note
    assert _clip(note, False) == note
    assert _clip(note, 0) == note
    assert _clip(note, 8) == "Trend t…"


def test_buy_note_refuses_bool_score() -> None:
    """tradermonty #700/#655: True→1.0 must not invent a ledger buy score."""
    ctx = buy_note_from_opportunity(
        {"strategy": "momentum", "score": True},
        source="scan",
    )
    assert "score" not in ctx
    ctx0 = buy_note_from_opportunity({"score": 0}, source="scan")
    assert ctx0["score"] == 0.0


def test_buy_note_prefers_scan_reasoning() -> None:
    ctx = buy_note_from_opportunity(
        {
            "strategy": "momentum",
            "reasoning": "+4.2% 24h momentum",
            "score": 33.5,
        },
        source="scan",
    )
    assert ctx["strategy"] == "momentum"
    assert ctx["note"] == "+4.2% 24h momentum"
    assert ctx["score"] == 33.5
    assert ctx["source"] == "scan"


def test_buy_note_prefers_recommender_reasons() -> None:
    ctx = buy_note_from_opportunity(
        {"strategy": "breakout", "reasoning": "scanner line"},
        source="rebalance",
        recommendation={
            "reasons": ["RS above benchmark"],
            "confidence": "HIGH",
            "score": 12,
        },
    )
    assert ctx["note"] == "RS above benchmark"
    assert ctx["confidence"] == "HIGH"
    assert ctx["source"] == "rebalance"


def test_buy_note_clips_long_ai_text() -> None:
    long = "x" * 200
    ctx = buy_note_from_opportunity({"ai_reasoning": long}, source="scan")
    assert len(ctx["note"]) <= 160
    assert ctx["note"].endswith("…")
