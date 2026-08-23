from stock_checker.trade_context import buy_note_from_opportunity


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
