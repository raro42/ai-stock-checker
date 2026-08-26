from stock_checker.trade_context import sell_note_from_exit


def test_sell_note_stop_loss() -> None:
    ctx = sell_note_from_exit(
        exit_reason="sl", profit_pct=-6.1, threshold=5.0
    )
    assert ctx["exit_reason"] == "sl"
    assert "Stop loss" in ctx["note"]
    assert "−5" in ctx["note"] or "-5" in ctx["note"]


def test_sell_note_trim_detail() -> None:
    ctx = sell_note_from_exit(
        exit_reason="trim",
        profit_pct=-3.0,
        detail="trim overweight (worst mark -3.00%)",
    )
    assert "trim overweight" in ctx["note"]
