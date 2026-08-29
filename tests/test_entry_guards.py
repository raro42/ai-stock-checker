from stock_checker.entry_guards import (
    ai_entry_allows,
    breakout_pullback_allows,
    parse_risk_pct_from_note,
    scan_entry_guards,
    scan_risk_allows,
)


def test_ai_blocks_hold_on_breakout() -> None:
    ok, why = ai_entry_allows("HOLD", "MEDIUM", strategy="breakout")
    assert not ok
    assert "BUY" in why


def test_ai_blocks_low_confidence_breakout() -> None:
    ok, why = ai_entry_allows("BUY", "LOW", strategy="breakout")
    assert not ok
    assert "breakout" in why.lower()


def test_ai_allows_buy_medium_breakout() -> None:
    ok, _ = ai_entry_allows("BUY", "MEDIUM", strategy="breakout")
    assert ok


def test_breakout_blocks_shallow_pullback() -> None:
    ok, why = breakout_pullback_allows(
        {"asset_class": "stock", "strategy": "breakout", "pct_from_high": -1.6}
    )
    assert not ok
    assert "extended" in why


def test_breakout_blocks_extended_peak() -> None:
    ok, why = breakout_pullback_allows(
        {"asset_class": "stock", "strategy": "breakout", "pct_from_high": -0.5}
    )
    assert not ok
    assert "extended" in why


def test_breakout_allows_pullback_band() -> None:
    ok, _ = breakout_pullback_allows(
        {"asset_class": "stock", "strategy": "breakout", "pct_from_high": -2.5}
    )
    assert ok


def test_scan_risk_blocks_tight_stop() -> None:
    ok, why = scan_risk_allows(
        {"risk_rr_ok": True, "risk_note": "stop swing €645 (−5.1%)"},
        stop_loss_pct=5.0,
    )
    assert not ok
    assert "tight" in why


def test_parse_risk_pct_from_note() -> None:
    assert parse_risk_pct_from_note("stop swing (−5.1%) · tgt +20%") == 5.1


def test_scan_entry_guards_caci_like_blocked() -> None:
    opp = {
        "asset_class": "stock",
        "strategy": "breakout",
        "pct_from_high": -0.5,
        "risk_rr_ok": True,
        "risk_note": "stop swing (−5.1%)",
        "ai_action": "HOLD",
        "ai_confidence": "LOW",
    }
    ok, why, mult = scan_entry_guards(
        opp, ai_action="HOLD", ai_confidence="LOW", stop_loss_pct=5.0
    )
    assert not ok
    assert "LOW" in why
    assert mult == 1.0
