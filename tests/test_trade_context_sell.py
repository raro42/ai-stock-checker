from stock_checker.trade_context import sell_note_from_exit


def test_sell_note_refuses_bool_profit_pct() -> None:
    """Bool profit/threshold must not invent +1.0% TP/SL note copy."""
    ctx = sell_note_from_exit(
        exit_reason="tp", profit_pct=True, threshold=8.0  # type: ignore[arg-type]
    )
    assert "Profit target" not in ctx.get("note", "")
    assert ctx["note"] == "tp"
    ctx_ok = sell_note_from_exit(
        exit_reason="tp", profit_pct=8.2, threshold=8.0
    )
    assert "Profit target +8.2%" in ctx_ok["note"]


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
