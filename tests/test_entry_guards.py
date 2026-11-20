import math

from stock_checker.entry_guards import (
    ai_entry_allows,
    breakout_pullback_allows,
    implied_risk_pct,
    parse_risk_pct_from_note,
    position_size_multiplier,
    scan_entry_guards,
    scan_risk_allows,
)


def test_ai_blocks_hold_on_breakout() -> None:
    ok, why = ai_entry_allows("HOLD", "MEDIUM", strategy="breakout")
    assert not ok
    assert "BUY" in why


def test_ai_off_allows_breakout_without_verdict() -> None:
    # AI mode off / backend down must not freeze stock breakouts.
    ok, why = ai_entry_allows(None, None, strategy="breakout")
    assert ok
    assert why == "AI off"
    ok2, _ = ai_entry_allows("unavailable", "LOW", strategy="breakout")
    assert ok2


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


def test_breakout_refuses_bool_nan_pct_fail_open() -> None:
    """tradermonty #798/#655: True→1.0 must not invent 'too extended'."""
    for bad in (True, False, math.nan, "n/a"):
        ok, why = breakout_pullback_allows(
            {"asset_class": "stock", "strategy": "breakout", "pct_from_high": bad}
        )
        assert ok
        assert "unreadable" in why


def test_implied_risk_refuses_bool_nan() -> None:
    """tradermonty #798/#655: True→1.0 must not invent a 1% implied stop."""
    assert implied_risk_pct({"risk_pct": True}) is None
    assert implied_risk_pct({"risk_pct": math.nan}) is None
    assert implied_risk_pct({"risk_pct": False}) is None
    assert implied_risk_pct({"risk_pct": -7.2}) == 7.2
    # Note path still works when risk_pct is unusable.
    assert (
        implied_risk_pct({"risk_pct": True, "risk_note": "stop swing (−5.1%)"})
        == 5.1
    )


def test_scan_risk_blocks_tight_stop() -> None:
    ok, why = scan_risk_allows(
        {"risk_rr_ok": True, "risk_note": "stop swing €645 (−5.1%)"},
        stop_loss_pct=5.0,
    )
    assert not ok
    assert "tight" in why


def test_scan_risk_and_size_refuse_bool_stop() -> None:
    """tradermonty #700/#655: True→1% must not invent a soft risk ceiling."""
    tight = {"risk_rr_ok": True, "risk_note": "stop swing (−5.1%)"}
    # Bool knob falls back to default 5% → ceiling 6% → 5.1% still too tight.
    ok, why = scan_risk_allows(tight, stop_loss_pct=True)  # type: ignore[arg-type]
    assert not ok
    assert "tight" in why
    assert "−5%" in why

    # Pre-fix: float(True)→1 → ceiling 2 → 5.1% would falsely pass.
    ok_false, _ = scan_risk_allows(tight, stop_loss_pct=1.0)
    assert ok_false

    wide = {"risk_pct": 9.0}
    # Default headroom 6% → 9/6 = 1.5 → full size; bool must not shrink headroom.
    assert position_size_multiplier(wide, stop_loss_pct=True) == 1.0  # type: ignore[arg-type]
    assert position_size_multiplier(wide, stop_loss_pct=math.nan) == 1.0
    # True→1% headroom 2 → ratio 9/2 capped at 1.0 still, but mid band changes:
    mid = {"risk_pct": 3.0}
    assert position_size_multiplier(mid, stop_loss_pct=5.0) == 0.5  # 3/6
    # Bool falls back to 5% (same 0.5), not True→1 → 3/2=1.0 fat size.
    assert position_size_multiplier(mid, stop_loss_pct=True) == 0.5  # type: ignore[arg-type]
    assert position_size_multiplier(mid, stop_loss_pct=1.0) == 1.0  # pre-fix invent


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
