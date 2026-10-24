"""Offline tests for Yahoo movers → universe discovery helpers."""

from stock_checker.yahoo_universe_discovery import (
    YahooScreenEmptyError,
    _quotes_from_screen_payload,
    bump_yahoo_fail_streak,
    classify_yahoo_discovery_error,
    clear_yahoo_discovery_error,
    clear_yahoo_fail_streak,
    discover_yahoo_mover_report,
    discover_yahoo_mover_symbols,
    screen_payload_failed,
    screens_bundle_failed,
    set_yahoo_discovery_error,
    yahoo_discovery_error_class,
    yahoo_fail_error_also_bit,
    yahoo_fail_error_also_counts,
    yahoo_fail_error_also_share,
    yahoo_fail_error_also_vs_delta,
    yahoo_fail_error_also_vs_delta_lead,
    yahoo_fail_error_also_vs_delta_lead_size,
    yahoo_fail_error_also_vs_delta_lead_size_sides,
    yahoo_fail_error_also_vs_delta_lead_size_sides_delta,
    yahoo_fail_error_also_vs_delta_lead_size_sides_share,
    yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta,
    yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap,
    yahoo_fail_mix_lean_meta,
    yahoo_fail_cascade_lean_meta,
    yahoo_fail_error_also_vs_lean,
    yahoo_fail_error_also_vs_winner,
    yahoo_fail_error_seed_fail_vs_budget,
    yahoo_fail_error_seed_vs_fail,
    yahoo_fail_error_vs_budget,
    yahoo_fail_error_vs_fail,
    yahoo_fail_error_vs_seed,
    yahoo_fail_streak,
    yahoo_fail_streak_seed_fail_vs_budget,
    yahoo_fail_streak_seed_vs_fail,
    yahoo_fail_streak_vs_budget,
    yahoo_fail_streak_vs_fail,
    yahoo_fail_streak_vs_seed,
)


def test_classify_yahoo_discovery_error_bundle_and_exc():
    """xang1234 #639: dead movers named by kind (empty/thin/timeout/http)."""
    assert (
        classify_yahoo_discovery_error(screens_ok=0, screens_failed=3) == "empty"
    )
    assert (
        classify_yahoo_discovery_error(screens_ok=1, screens_failed=2) == "thin"
    )
    assert (
        classify_yahoo_discovery_error(
            screens_ok=0, screens_failed=3, timeout_fails=3
        )
        == "timeout"
    )
    assert (
        classify_yahoo_discovery_error(
            screens_ok=0, screens_failed=3, timeout_fails=2
        )
        == "timeout"
    )
    assert (
        classify_yahoo_discovery_error(
            screens_ok=0, screens_failed=3, timeout_fails=1
        )
        == "empty"
    )
    assert (
        classify_yahoo_discovery_error(
            screens_ok=0, screens_failed=3, inflight_fails=3
        )
        == "inflight"
    )
    assert (
        classify_yahoo_discovery_error(
            screens_ok=0, screens_failed=3, timeout_fails=1, inflight_fails=2
        )
        == "inflight"
    )
    assert (
        classify_yahoo_discovery_error(
            screens_ok=0, screens_failed=3, timeout_fails=2, inflight_fails=1
        )
        == "timeout"
    )
    assert classify_yahoo_discovery_error(TimeoutError("timed out")) == "timeout"
    assert (
        classify_yahoo_discovery_error(
            TimeoutError("yahoo screen day_gainers still in flight — timed out")
        )
        == "inflight"
    )
    assert classify_yahoo_discovery_error(RuntimeError("HTTP 403")) == "http"
    # FinRobot #119: 402 / payment-required is plan entitlement, not http flake.
    assert classify_yahoo_discovery_error(RuntimeError("HTTP 402")) == "plan"
    assert (
        classify_yahoo_discovery_error(
            RuntimeError("HTTP Error 402: Payment Required")
        )
        == "plan"
    )
    assert (
        classify_yahoo_discovery_error(
            RuntimeError("FMP account payment/plan access required")
        )
        == "plan"
    )
    assert classify_yahoo_discovery_error(YahooScreenEmptyError("empty")) == "empty"
    assert classify_yahoo_discovery_error(RuntimeError("boom")) == "error"


def test_set_yahoo_discovery_error_allows_plan():
    """plan is allowlisted so desk can speak it (not coerced to error)."""
    meta: dict = {}
    assert set_yahoo_discovery_error(meta, "plan") == "plan"
    assert meta["last_yahoo_discovery_error"] == "plan"
    assert yahoo_discovery_error_class(meta) == "plan"


def test_yahoo_fail_error_also_bit_timeout_inflight_mix():
    """Winning class alone hid the other spend side (xang1234 #639)."""
    assert (
        yahoo_fail_error_also_bit(
            "inflight", timeout_fails=1, inflight_fails=2
        )
        == "+timeout"
    )
    assert (
        yahoo_fail_error_also_bit(
            "timeout", timeout_fails=2, inflight_fails=1
        )
        == "+held"
    )
    assert (
        yahoo_fail_error_also_bit(
            "inflight", timeout_fails=0, inflight_fails=3
        )
        == ""
    )
    assert (
        yahoo_fail_error_also_bit(
            "timeout", timeout_fails=3, inflight_fails=0
        )
        == ""
    )
    assert (
        yahoo_fail_error_also_bit("empty", timeout_fails=1, inflight_fails=1)
        == ""
    )


def test_yahoo_fail_error_also_share_hidden_side():
    """+timeout / +held alone hid whether the other spend is half or a sliver."""
    assert yahoo_fail_error_also_share(
        "inflight", timeout_fails=1, inflight_fails=1
    ) == ("hot · 50%", 50, "hot")
    assert yahoo_fail_error_also_share(
        "timeout", timeout_fails=3, inflight_fails=1
    ) == ("quiet · 25%", 25, "quiet")
    assert yahoo_fail_error_also_share(
        "timeout", timeout_fails=2, inflight_fails=1
    ) == ("33%", 33, "ok")
    assert yahoo_fail_error_also_share(
        "inflight", timeout_fails=0, inflight_fails=3
    ) == ("", None, "")
    assert yahoo_fail_error_also_share(
        "empty", timeout_fails=1, inflight_fails=1
    ) == ("", None, "")
    assert yahoo_fail_error_also_share("timeout", timeout_fails="x", inflight_fails=1) == (
        "",
        None,
        "",
    )


def test_yahoo_fail_error_also_vs_winner_named_share():
    """Hidden % alone hid the named class's ownership of the mix."""
    assert yahoo_fail_error_also_vs_winner(
        "inflight", timeout_fails=1, inflight_fails=2
    ) == ("vs inflight · 67%", 67, "ok")
    assert yahoo_fail_error_also_vs_winner(
        "timeout", timeout_fails=3, inflight_fails=1
    ) == ("vs timeout · strong · 75%", 75, "strong")
    assert yahoo_fail_error_also_vs_winner(
        "inflight", timeout_fails=1, inflight_fails=1
    ) == ("vs inflight · 50%", 50, "ok")
    assert yahoo_fail_error_also_vs_winner(
        "inflight", timeout_fails=0, inflight_fails=3
    ) == ("", None, "")
    assert yahoo_fail_error_also_vs_winner(
        "empty", timeout_fails=1, inflight_fails=1
    ) == ("", None, "")
    assert yahoo_fail_error_also_vs_winner(
        "timeout", timeout_fails="x", inflight_fails=1
    ) == ("", None, "")


def test_yahoo_fail_error_also_counts_scale():
    """Mix % hid one hung screen versus a wide timeout/inflight outage."""
    assert (
        yahoo_fail_error_also_counts(
            "inflight", timeout_fails=1, inflight_fails=2
        )
        == "1 timeout · 2 held"
    )
    assert (
        yahoo_fail_error_also_counts(
            "timeout", timeout_fails=8, inflight_fails=8
        )
        == "8 timeout · 8 held"
    )
    assert (
        yahoo_fail_error_also_counts("timeout", timeout_fails=2, inflight_fails=0)
        == ""
    )
    assert (
        yahoo_fail_error_also_counts("empty", timeout_fails=1, inflight_fails=1)
        == ""
    )
    assert (
        yahoo_fail_error_also_counts("timeout", timeout_fails="x", inflight_fails=1)
        == ""
    )


def test_yahoo_fail_error_also_vs_lean_extremes():
    """Hidden % beside winner % hid quiet-agrees-strong and a 50/50 overclaim."""
    assert yahoo_fail_error_also_vs_lean("quiet", "strong") == (
        "align · quiet|strong",
        False,
    )
    assert yahoo_fail_error_also_vs_lean("hot", "ok") == (
        "clash · hidden hot · winner ok",
        True,
    )
    assert yahoo_fail_error_also_vs_lean("ok", "ok") == ("", False)
    assert yahoo_fail_error_also_vs_lean("", "strong") == ("", False)
    assert yahoo_fail_error_also_vs_lean("quiet", "ok") == (
        "clash · hidden quiet · winner ok",
        False,
    )


def test_yahoo_fail_error_also_vs_delta_spread():
    """Lean labels hid a wide quiet|strong gap and a 50/50 that sits together."""
    assert yahoo_fail_error_also_vs_delta(25, 75) == (
        "Δ wide · -50pp",
        -50,
        "wide",
    )
    assert yahoo_fail_error_also_vs_delta(50, 50) == ("Δ thin · 0pp", 0, "thin")
    assert yahoo_fail_error_also_vs_delta(60, 40) == (
        "Δ wide · +20pp",
        20,
        "wide",
    )
    assert yahoo_fail_error_also_vs_delta(55, 45) == ("", None, "")
    assert yahoo_fail_error_also_vs_delta(None, 75) == ("", None, "")


def test_yahoo_fail_error_also_vs_delta_lead_names_louder_side():
    """Signed Δ hid whether timeout or held owns the spread."""
    assert yahoo_fail_error_also_vs_delta_lead("inflight", -50, "wide") == (
        "Δ lead · held"
    )
    assert yahoo_fail_error_also_vs_delta_lead("timeout", 20, "wide") == (
        "Δ lead · held"
    )
    assert yahoo_fail_error_also_vs_delta_lead("timeout", -50, "wide") == (
        "Δ lead · timeout"
    )
    assert yahoo_fail_error_also_vs_delta_lead("timeout", 0, "thin") == ""
    assert yahoo_fail_error_also_vs_delta_lead("timeout", 15, "") == ""
    assert yahoo_fail_error_also_vs_delta_lead("empty", -50, "wide") == ""


def test_yahoo_fail_error_also_vs_delta_lead_size_ratio():
    """Lead name hid a 3× ownership gap versus a near tie."""
    assert yahoo_fail_error_also_vs_delta_lead_size(
        "Δ lead · held", 25, 75
    ) == ("Δ lead size · 3×", 3.0)
    assert yahoo_fail_error_also_vs_delta_lead_size(
        "Δ lead · timeout", 40, 60
    ) == ("Δ lead size · 1.5×", 1.5)
    assert yahoo_fail_error_also_vs_delta_lead_size("", 25, 75) == ("", None)
    assert yahoo_fail_error_also_vs_delta_lead_size(
        "Δ lead · held", 0, 100
    ) == ("", None)
    assert yahoo_fail_error_also_vs_delta_lead_size(
        "Δ lead · held", None, 75
    ) == ("", None)
    # 1 and 7 round to 13% and 88% → 6.77×; counts are 7×.
    assert yahoo_fail_error_also_vs_delta_lead_size(
        "Δ lead · held", 13, 88, timeout_fails=1, inflight_fails=7
    ) == ("Δ lead size · 7×", 7.0)
    assert yahoo_fail_error_also_vs_delta_lead_size(
        "Δ lead · held", 13, 88, timeout_fails=0, inflight_fails=0
    ) == ("Δ lead size · 6.77×", 6.77)


def test_yahoo_fail_error_also_vs_delta_lead_size_sides_both_shares():
    """A 3× ratio hid the two spend sides; counts beat rounded percents."""
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        3.0, "inflight", 25, 75
    ) == (
        "Δ lead size sides · held 75% · timeout 25%",
        75,
        25,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        7.0,
        "inflight",
        12,
        88,
        timeout_fails=1,
        inflight_fails=7,
    ) == (
        "Δ lead size sides · held 7 · timeout 1",
        7,
        1,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        3.0,
        "inflight",
        25,
        75,
        timeout_fails=1,
        inflight_fails=3,
    ) == (
        "Δ lead size sides · held 3 · timeout 1",
        3,
        1,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        1.5, "timeout", 40, 60
    ) == (
        "Δ lead size sides · timeout 60% · held 40%",
        60,
        40,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        None, "inflight", 25, 75
    ) == (
        "",
        None,
        None,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        3.0, "inflight", 0, 100
    ) == (
        "",
        None,
        None,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides(
        3.0, "empty", 25, 75
    ) == (
        "",
        None,
        None,
    )


def test_yahoo_fail_error_also_vs_delta_lead_size_sides_delta_count_gap():
    """Rounded pp width hid a one-screen gap; percent sides stay silent."""
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_delta(
        "Δ lead size sides · held 3 · timeout 2", 3, 2
    ) == (
        "Δ lead size sides Δ thin · 1 screen",
        1,
        "thin",
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_delta(
        "Δ lead size sides · held 7 · timeout 1", 7, 1
    ) == (
        "Δ lead size sides Δ wide · 6 screens",
        6,
        "wide",
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_delta(
        "Δ lead size sides · held 75% · timeout 25%", 75, 25
    ) == ("", None, "")
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_delta("", 7, 1) == (
        "",
        None,
        "",
    )


def test_yahoo_fail_error_also_vs_delta_lead_size_sides_share_count_pair():
    """Same screen gap can be a concentrated mix or a mild one."""
    wide = "Δ lead size sides Δ wide · 6 screens"
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share(
        wide, "Δ lead size sides · held 7 · timeout 1", 7, 1
    ) == (
        "Δ lead size sides share · held 88% · timeout 12%",
        88,
        12,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share(
        wide, "Δ lead size sides · timeout 20 · held 14", 20, 14
    ) == (
        "Δ lead size sides share · timeout 59% · held 41%",
        59,
        41,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share(
        "Δ lead size sides Δ thin · 1 screen",
        "Δ lead size sides · held 75% · timeout 25%",
        75,
        25,
    ) == ("", None, None)
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share(
        "", "Δ lead size sides · held 7 · timeout 1", 7, 1
    ) == ("", None, None)


def test_yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta_spread():
    """Named % alone hid a lopsided pair vs a near-even mix."""
    wide_share = "Δ lead size sides share · held 88% · timeout 12%"
    mild_share = "Δ lead size sides share · timeout 59% · held 41%"
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta(
        wide_share, 88, 12
    ) == (
        "Δ lead size sides share Δ wide · +76pp",
        76,
        "wide",
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta(
        mild_share, 59, 41
    ) == ("", None, "")
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta(
        "Δ lead size sides share · held 52% · timeout 48%", 52, 48
    ) == (
        "Δ lead size sides share Δ thin · +4pp",
        4,
        "thin",
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta(
        "", 88, 12
    ) == ("", None, "")


def test_yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap():
    """Screen-gap severity ≠ ownership-spread severity.

    Wide agreement warns (lopsided outage confirmed). Thin agreement stays calm.
    """
    share_wide = "Δ lead size sides share Δ wide · +76pp"
    share_thin = "Δ lead size sides share Δ thin · +4pp"
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
        share_wide, "wide", "wide"
    ) == (
        "align",
        "Δ lead size sides share vs gap align · wide",
        True,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
        share_thin, "thin", "thin"
    ) == (
        "align",
        "Δ lead size sides share vs gap align · thin",
        False,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
        share_wide, "wide", "thin"
    ) == (
        "clash",
        "Δ lead size sides share vs gap clash · screens thin · % wide",
        True,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
        share_thin, "thin", "wide"
    ) == (
        "clash",
        "Δ lead size sides share vs gap clash · screens wide · % thin",
        True,
    )
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
        "", "wide", "wide"
    ) == ("", "", False)
    assert yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap(
        share_wide, "mid", "wide"
    ) == ("", "", False)


def test_yahoo_fail_mix_lean_meta_names_the_open():
    """Quiet chip names spoken stages; a warned open names align or clash."""
    wide = "Δ lead size sides share vs gap align · wide"
    clash = "Δ lead size sides share vs gap clash · screens thin · % wide"
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap="",
        share_vs_gap_verb="",
        share_vs_gap_warn=False,
        lean_warn=False,
    ) == "quiet"
    body = "+timeout · 1 timeout · 2 held · 33% · vs inflight · 67%"
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap="",
        share_vs_gap_verb="",
        share_vs_gap_warn=False,
        lean_warn=False,
        mix_lean=body,
    ) == "quiet · 4 folds · +timeout · counts · share · vs"
    long_body = (
        "+held · 7 timeout · 1 held · clash · hidden hot · winner ok"
        " · Δ wide · -76pp · Δ lead · held · Δ lead size · 7×"
        " · Δ lead size sides · held 7 · timeout 1"
    )
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap="",
        share_vs_gap_verb="",
        share_vs_gap_warn=False,
        lean_warn=False,
        mix_lean=long_body,
    ) == "quiet · 7 folds · +held · counts · lean · Δ · +3"
    # Hot lean without spoken stages stays lean-only.
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap="",
        share_vs_gap_verb="",
        share_vs_gap_warn=False,
        lean_warn=True,
    ) == "clash"
    # Hot lean appends spoken stages (Screener weight hot inventory).
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap="",
        share_vs_gap_verb="",
        share_vs_gap_warn=False,
        lean_warn=True,
        mix_lean=body,
    ) == "clash · +timeout · counts · share · vs"
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap=wide,
        share_vs_gap_verb="align",
        share_vs_gap_warn=True,
        lean_warn=True,
        mix_lean=body,
    ) == "align · wide · +timeout · counts · share · vs"
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap=clash,
        share_vs_gap_verb="clash",
        share_vs_gap_warn=True,
        lean_warn=False,
        mix_lean=long_body,
    ) == "clash · +held · counts · lean · Δ · +3"
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap=clash,
        share_vs_gap_verb="clash",
        share_vs_gap_warn=True,
        lean_warn=False,
    ) == "clash"
    assert yahoo_fail_mix_lean_meta(
        share_vs_gap="Δ lead size sides share vs gap align · thin",
        share_vs_gap_verb="align",
        share_vs_gap_warn=False,
        lean_warn=False,
        mix_lean=body,
    ) == "quiet · 4 folds · +timeout · counts · share · vs"


def test_yahoo_fail_cascade_lean_meta_names_the_open():
    """Quiet chip names spoken stages; warned sf/budget or seed/fail names why."""
    assert yahoo_fail_cascade_lean_meta() == "quiet"
    assert yahoo_fail_cascade_lean_meta(
        lean="error/seed clash · fresh · error/budget align · due"
    ) == "quiet · 2 folds · seed · budget"
    assert yahoo_fail_cascade_lean_meta(
        lean="streak/seed align · stale"
    ) == "quiet · 1 fold · seed"
    assert yahoo_fail_cascade_lean_meta(
        lean=(
            "error/seed align · stale · error/fail align · fresh"
            " · error seed/fail align · both align"
            " · error/budget clash · held · not spent"
            " · error sf/budget align · both align"
        )
    ) == "quiet · 5 folds · seed · fail · seed/fail · budget · +1"
    # Hot lean without spoken stages stays lean-only.
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="align · both clash",
            outer_warn=True,
        )
        == "align · both clash"
    )
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="align · both align",
            outer_warn=True,
        )
        == "align · both align"
    )
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="clash · seed/fail align · budget clash",
            outer_warn=True,
        )
        == "clash"
    )
    # Hot cascade appends spoken stages (mix / Screener weight hot inventory).
    cascade_body = (
        "error/seed align · stale · error/fail align · fresh"
        " · error seed/fail align · both align"
        " · error/budget clash · held · not spent"
        " · error sf/budget align · both clash"
    )
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="align · both clash",
            outer_warn=True,
            lean=cascade_body,
        )
        == "align · both clash · seed · fail · seed/fail · budget · +1"
    )
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="clash · seed/fail align · budget clash",
            outer_warn=True,
            lean="streak/seed align · stale · streak/budget clash · held · not spent",
        )
        == "clash · seed · budget"
    )
    # Outer warn wins over inner.
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="align · both clash",
            outer_warn=True,
            inner_bit="clash · seed clash · fail align",
            inner_warn=True,
            lean="streak/seed align · stale",
        )
        == "align · both clash · seed"
    )
    # Inner alone when outer quiet.
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="",
            outer_warn=False,
            inner_bit="clash · seed clash · fail align",
            inner_warn=True,
        )
        == "clash"
    )
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="",
            outer_warn=False,
            inner_bit="clash · seed clash · fail align",
            inner_warn=True,
            lean="streak/seed clash · fresh · seed/fail clash · seed clash · fail align",
        )
        == "clash · seed · seed/fail"
    )
    # Non-warn outer does not open the chip; the body names what spoke.
    assert (
        yahoo_fail_cascade_lean_meta(
            outer_bit="align · both align",
            outer_warn=False,
            inner_bit="",
            inner_warn=False,
            lean="streak/seed align · stale · seed/fail align · both align",
        )
        == "quiet · 2 folds · seed · seed/fail"
    )


def test_yahoo_discovery_error_meta_allowlist():
    """Only allowlisted classes persist; junk meta stays silent on glance."""
    meta: dict = {}
    assert set_yahoo_discovery_error(meta, "empty") == "empty"
    assert yahoo_discovery_error_class(meta) == "empty"
    assert set_yahoo_discovery_error(meta, "DROP TABLE;") == "error"
    assert yahoo_discovery_error_class(meta) == "error"
    clear_yahoo_discovery_error(meta)
    assert yahoo_discovery_error_class(meta) == ""
    assert yahoo_discovery_error_class({"last_yahoo_discovery_error": "nope"}) == ""


def test_yahoo_fail_streak_bump_and_clear():
    """xang1234 #639: consecutive fails are counted; success resets."""
    assert yahoo_fail_streak(None) == 0
    assert yahoo_fail_streak({}) == 0
    assert yahoo_fail_streak({"yahoo_discovery_fail_streak": "nope"}) == 0
    meta: dict = {}
    assert bump_yahoo_fail_streak(meta) == 1
    assert bump_yahoo_fail_streak(meta) == 2
    assert yahoo_fail_streak(meta) == 2
    clear_yahoo_fail_streak(meta)
    assert yahoo_fail_streak(meta) == 0


def test_yahoo_fail_error_vs_seed_extremes():
    """Typed last-error vs seed: fresh clash / stale align (first-fail honesty)."""
    assert yahoo_fail_error_vs_seed("timeout", "fresh") == "clash · fresh"
    assert yahoo_fail_error_vs_seed("empty", "stale") == "align · stale"
    assert yahoo_fail_error_vs_seed("http", "aging") == ""
    assert yahoo_fail_error_vs_seed("thin", "never") == ""
    assert yahoo_fail_error_vs_seed("", "fresh") == ""
    assert yahoo_fail_error_vs_seed("DROP TABLE;", "fresh") == ""
    assert yahoo_fail_error_vs_seed("error", "unknown") == ""


def test_yahoo_fail_error_vs_fail_extremes():
    """Typed last-error vs fail stamp: fresh align / stale clash (first-fail)."""
    assert yahoo_fail_error_vs_fail("timeout", "fresh") == "align · fresh"
    assert yahoo_fail_error_vs_fail("empty", "stale") == "clash · stale"
    assert yahoo_fail_error_vs_fail("http", "aging") == ""
    assert yahoo_fail_error_vs_fail("thin", "never") == ""
    assert yahoo_fail_error_vs_fail("", "fresh") == ""
    assert yahoo_fail_error_vs_fail("DROP TABLE;", "fresh") == ""
    assert yahoo_fail_error_vs_fail("error", "unknown") == ""


def test_yahoo_fail_error_seed_vs_fail_extremes():
    """error seed/fail meta reuses streak helper (same verb grammar)."""
    bit, warn = yahoo_fail_error_seed_vs_fail("clash · fresh", "align · fresh")
    assert bit == "clash · seed clash · fail align"
    assert warn is True
    bit, warn = yahoo_fail_error_seed_vs_fail("align · stale", "align · fresh")
    assert bit == "align · both align"
    assert warn is False
    bit, warn = yahoo_fail_error_seed_vs_fail("clash · fresh", "clash · stale")
    assert bit == "align · both clash"
    assert warn is True
    assert yahoo_fail_error_seed_vs_fail("", "align · fresh") == ("", False)
    assert yahoo_fail_error_seed_vs_fail("clash · fresh", "") == ("", False)


def test_yahoo_fail_streak_vs_seed_extremes():
    """N× vs seed: fresh clash / stale align; mid aging silent."""
    assert yahoo_fail_streak_vs_seed(1, "fresh") == ""
    assert yahoo_fail_streak_vs_seed(3, "fresh") == "clash · fresh"
    assert yahoo_fail_streak_vs_seed(3, "stale") == "align · stale"
    assert yahoo_fail_streak_vs_seed(3, "aging") == ""
    assert yahoo_fail_streak_vs_seed(3, "never") == ""
    assert yahoo_fail_streak_vs_seed("nope", "fresh") == ""


def test_yahoo_fail_streak_vs_fail_extremes():
    """N× vs fail stamp: fresh align / stale clash (inverted vs seed)."""
    assert yahoo_fail_streak_vs_fail(1, "fresh") == ""
    assert yahoo_fail_streak_vs_fail(3, "fresh") == "align · fresh"
    assert yahoo_fail_streak_vs_fail(3, "stale") == "clash · stale"
    assert yahoo_fail_streak_vs_fail(3, "aging") == ""
    assert yahoo_fail_streak_vs_fail(3, "never") == ""
    assert yahoo_fail_streak_vs_fail("nope", "fresh") == ""


def test_yahoo_fail_error_seed_fail_vs_budget_extremes():
    """error sf/budget reuses streak helper (same verb + both-clash-due warn)."""
    bit, warn = yahoo_fail_error_seed_fail_vs_budget(
        "align · both clash", "align · due"
    )
    assert bit == "align · both align"
    assert warn is True
    bit, warn = yahoo_fail_error_seed_fail_vs_budget(
        "clash · seed clash · fail align", "clash · held · not spent"
    )
    assert bit == "align · both clash"
    assert warn is True
    assert yahoo_fail_error_seed_fail_vs_budget("", "align · due") == ("", False)
    assert yahoo_fail_error_seed_fail_vs_budget("align · both align", "") == (
        "",
        False,
    )


def test_yahoo_fail_error_vs_budget_extremes():
    """First-fail typed death vs fetch budget (streak/budget stays silent)."""
    held = dict(retry_due=False, retry_remain_sec=1800)
    due = dict(retry_due=True, retry_remain_sec=0)
    assert yahoo_fail_error_vs_budget("timeout", **held) == (
        "clash · held · not spent"
    )
    assert yahoo_fail_error_vs_budget("empty", **due) == "align · due"
    assert yahoo_fail_error_vs_budget("", **held) == ""
    assert yahoo_fail_error_vs_budget("DROP TABLE;", **due) == ""
    assert (
        yahoo_fail_error_vs_budget("http", retry_due=False, retry_remain_sec=None)
        == ""
    )
    assert (
        yahoo_fail_error_vs_budget("error", retry_due=False, retry_remain_sec=0)
        == ""
    )
    # FinRobot #119: plan stays held even when remain is 0 / retry_due True.
    assert (
        yahoo_fail_error_vs_budget("plan", retry_due=True, retry_remain_sec=0)
        == "clash · held · not spent"
    )


def test_yahoo_fail_streak_vs_budget_extremes():
    """N× vs fetch budget: cooling held clash / retry-due align (xang1234 #640)."""
    assert (
        yahoo_fail_streak_vs_budget(1, retry_due=False, retry_remain_sec=1800) == ""
    )
    assert (
        yahoo_fail_streak_vs_budget(3, retry_due=False, retry_remain_sec=1800)
        == "clash · held · not spent"
    )
    assert (
        yahoo_fail_streak_vs_budget(3, retry_due=True, retry_remain_sec=0)
        == "align · due"
    )
    assert (
        yahoo_fail_streak_vs_budget(3, retry_due=True, retry_remain_sec=None)
        == "align · due"
    )
    assert (
        yahoo_fail_streak_vs_budget(3, retry_due=False, retry_remain_sec=None) == ""
    )
    assert (
        yahoo_fail_streak_vs_budget(3, retry_due=False, retry_remain_sec=0) == ""
    )
    assert (
        yahoo_fail_streak_vs_budget("nope", retry_due=False, retry_remain_sec=1800)
        == ""
    )


def test_yahoo_fail_streak_seed_vs_fail_extremes():
    """seed/fail meta: same verb align · both; crossed clash; missing silent."""
    bit, warn = yahoo_fail_streak_seed_vs_fail("clash · fresh", "align · fresh")
    assert bit == "clash · seed clash · fail align"
    assert warn is True
    bit, warn = yahoo_fail_streak_seed_vs_fail("align · stale", "align · fresh")
    assert bit == "align · both align"
    assert warn is False
    bit, warn = yahoo_fail_streak_seed_vs_fail("clash · fresh", "clash · stale")
    assert bit == "align · both clash"
    assert warn is True
    assert yahoo_fail_streak_seed_vs_fail("", "align · fresh") == ("", False)
    assert yahoo_fail_streak_seed_vs_fail("clash · fresh", "") == ("", False)
    assert yahoo_fail_streak_seed_vs_fail("aging · fresh", "align · fresh") == (
        "",
        False,
    )


def test_yahoo_fail_streak_seed_fail_vs_budget_extremes():
    """sf/budget meta: same outer verb align · both; crossed clash; missing silent."""
    # Outer verbs both clash → dual-clash warn.
    bit, warn = yahoo_fail_streak_seed_fail_vs_budget(
        "clash · seed clash · fail align", "clash · held"
    )
    assert bit == "align · both clash"
    assert warn is True
    # Outer both-align + calm seed/fail stays calm.
    bit, warn = yahoo_fail_streak_seed_fail_vs_budget(
        "align · both align", "align · due"
    )
    assert bit == "align · both align"
    assert warn is False
    # Outer both-align with seed/fail dual-clash under due → warn
    # (soft-allow both-clash warn parity; about-to-spend ≠ quiet confirm).
    bit, warn = yahoo_fail_streak_seed_fail_vs_budget(
        "align · both clash", "align · due"
    )
    assert bit == "align · both align"
    assert warn is True
    # Crossed outer verbs warn.
    bit, warn = yahoo_fail_streak_seed_fail_vs_budget(
        "align · both clash", "clash · held"
    )
    assert bit == "clash · seed/fail align · budget clash"
    assert warn is True
    bit, warn = yahoo_fail_streak_seed_fail_vs_budget(
        "clash · seed clash · fail align", "align · due"
    )
    assert bit == "clash · seed/fail clash · budget align"
    assert warn is True
    assert yahoo_fail_streak_seed_fail_vs_budget("", "clash · held") == (
        "",
        False,
    )
    assert yahoo_fail_streak_seed_fail_vs_budget(
        "align · both align", ""
    ) == ("", False)
    assert yahoo_fail_streak_seed_fail_vs_budget(
        "aging · both", "align · due"
    ) == ("", False)


def test_quotes_from_screen_payload():
    assert _quotes_from_screen_payload(None) == []
    assert _quotes_from_screen_payload({"quotes": [{"symbol": "AAPL"}]})[0]["symbol"] == "AAPL"


def test_screen_payload_failed_empty_or_thin():
    assert screen_payload_failed(None, expected=25) is True
    assert screen_payload_failed({"quotes": []}, expected=25) is True
    assert screen_payload_failed(
        {"quotes": [{"symbol": "AAPL"}, {"symbol": "MSFT"}]}, expected=25
    ) is True
    fat = {"quotes": [{"symbol": f"S{i}"} for i in range(10)]}
    assert screen_payload_failed(fat, expected=25) is False


def test_discover_yahoo_mover_symbols_mocked(monkeypatch):
    def fake_fetch(screen: str, *, count: int = 25, timeout_sec=None):
        if screen == "day_gainers":
            return ["AAPL", "USDT"]  # USDT filtered by is_tradeable
        if screen == "day_losers":
            return ["MSFT", "AAPL"]
        return ["NVDA"]

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.fetch_yahoo_screen_symbols",
        fake_fetch,
    )
    syms = discover_yahoo_mover_symbols(
        screens=("day_gainers", "day_losers", "most_actives"), per_screen=5
    )
    assert syms == ["AAPL", "MSFT", "NVDA"]


def test_discover_yahoo_mover_report_all_empty_is_failed(monkeypatch):
    def boom(screen: str, *, count: int = 25, timeout_sec=None):
        raise YahooScreenEmptyError(screen)

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.fetch_yahoo_screen_symbols",
        boom,
    )
    symbols, ok, failed, timeouts, inflight = discover_yahoo_mover_report(
        screens=("day_gainers", "day_losers"), per_screen=5
    )
    assert symbols == []
    assert ok == 0
    assert failed == 2
    assert timeouts == 0
    assert inflight == 0
    assert screens_bundle_failed(ok, failed) is True


def test_discover_yahoo_mover_report_counts_timeouts(monkeypatch):
    """xang1234 #639: hung screens count as timeout_fails (not quiet empty)."""

    def hang(screen: str, *, count: int = 25, timeout_sec=None):
        raise TimeoutError(f"yahoo screen {screen} timed out")

    monkeypatch.setattr(
        "stock_checker.yahoo_universe_discovery.fetch_yahoo_screen_symbols",
        hang,
    )
    symbols, ok, failed, timeouts, inflight = discover_yahoo_mover_report(
        screens=("day_gainers", "day_losers"), per_screen=5
    )
    assert symbols == []
    assert ok == 0
    assert failed == 2
    assert timeouts == 2
    assert inflight == 0
    assert (
        classify_yahoo_discovery_error(
            screens_ok=ok, screens_failed=failed, timeout_fails=timeouts
        )
        == "timeout"
    )


def test_screens_bundle_failed_majority_or_empty():
    assert screens_bundle_failed(0, 3) is True
    assert screens_bundle_failed(1, 2) is True
    assert screens_bundle_failed(2, 1) is False
    assert screens_bundle_failed(3, 0) is False


def test_screens_bundle_partial_minority_fail():
    from stock_checker.yahoo_universe_discovery import screens_bundle_partial

    assert screens_bundle_partial(2, 1) is True
    assert screens_bundle_partial(3, 0) is False
    assert screens_bundle_partial(1, 2) is False
    assert screens_bundle_partial(0, 3) is False


def test_yahoo_cache_freshness_seed_age_bands():
    from stock_checker.yahoo_universe_discovery import yahoo_cache_freshness

    assert yahoo_cache_freshness(None) == "never"
    assert yahoo_cache_freshness(0, parsed=False) == "unknown"
    assert yahoo_cache_freshness(6 * 3600) == "fresh"
    assert yahoo_cache_freshness(30 * 3600) == "aging"
    assert yahoo_cache_freshness(50 * 3600) == "stale"


def test_yahoo_discovery_due_from_meta_failed_skips_throttle():
    from datetime import datetime, timezone

    from stock_checker.yahoo_universe_discovery import (
        yahoo_discovery_due_from_meta,
        yahoo_fail_retry_remaining_sec,
    )

    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    fresh = "2026-10-04T06:00:00"
    assert yahoo_discovery_due_from_meta(
        {"last_yahoo_discovery": fresh, "last_yahoo_discovery_status": "ok"},
        now=now,
        max_age_hours=24,
    ) is False
    # Failed without fail stamp → retry immediately (cannot apply backoff).
    assert yahoo_discovery_due_from_meta(
        {"last_yahoo_discovery": fresh, "last_yahoo_discovery_status": "failed"},
        now=now,
        max_age_hours=24,
    ) is True
    assert yahoo_fail_retry_remaining_sec(
        {"last_yahoo_discovery_status": "failed"},
        now=now,
    ) is None
    assert yahoo_discovery_due_from_meta(None, now=now) is True
    assert yahoo_discovery_due_from_meta({}, now=now) is True


def test_yahoo_discovery_due_from_meta_fail_backoff():
    """xang1234 dfb6a86: do not refetch empty/dead Yahoo every scan."""
    from datetime import datetime, timezone

    from stock_checker.yahoo_universe_discovery import (
        yahoo_discovery_due_from_meta,
        yahoo_fail_retry_remaining_sec,
    )

    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    seed = "2026-10-04T06:00:00"
    # Fail 15m ago → still inside 1h backoff.
    recent_fail = "2026-10-04T11:45:00"
    meta_cooling = {
        "last_yahoo_discovery": seed,
        "last_yahoo_discovery_status": "failed",
        "last_yahoo_discovery_fail": recent_fail,
    }
    assert yahoo_discovery_due_from_meta(meta_cooling, now=now) is False
    remain = yahoo_fail_retry_remaining_sec(meta_cooling, now=now)
    assert remain == 45 * 60
    # Fail 90m ago → backoff elapsed → retry due.
    old_fail = "2026-10-04T10:30:00"
    meta_due = {
        "last_yahoo_discovery": seed,
        "last_yahoo_discovery_status": "failed",
        "last_yahoo_discovery_fail": old_fail,
    }
    assert yahoo_discovery_due_from_meta(meta_due, now=now) is True
    assert yahoo_fail_retry_remaining_sec(meta_due, now=now) == 0


def test_yahoo_discovery_due_from_meta_plan_held():
    """FinRobot #119: plan fail never auto-due after backoff."""
    from datetime import datetime, timezone

    from stock_checker.yahoo_universe_discovery import (
        yahoo_discovery_due_from_meta,
        yahoo_fail_plan_held,
        yahoo_fail_retry_remaining_sec,
    )

    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    seed = "2026-10-04T06:00:00"
    old_fail = "2026-10-04T10:30:00"
    meta_plan = {
        "last_yahoo_discovery": seed,
        "last_yahoo_discovery_status": "failed",
        "last_yahoo_discovery_fail": old_fail,
        "last_yahoo_discovery_error": "plan",
    }
    assert yahoo_fail_plan_held(meta_plan) is True
    assert yahoo_fail_retry_remaining_sec(meta_plan, now=now) == 0
    assert yahoo_discovery_due_from_meta(meta_plan, now=now) is False
    # http after the same stamp still becomes due.
    meta_http = dict(meta_plan)
    meta_http["last_yahoo_discovery_error"] = "http"
    assert yahoo_fail_plan_held(meta_http) is False
    assert yahoo_discovery_due_from_meta(meta_http, now=now) is True


def test_fetch_yahoo_screen_403_is_empty_error(monkeypatch):
    import pytest

    from stock_checker.yahoo_universe_discovery import fetch_yahoo_screen_symbols

    class _YF:
        @staticmethod
        def screen(screen, count=25):
            raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _YF)
    with pytest.raises(YahooScreenEmptyError):
        fetch_yahoo_screen_symbols("day_gainers", count=5)


def test_fetch_yahoo_screen_timeout_raises(monkeypatch):
    """xang1234 #639: hung yf.screen cannot stall the scan join forever."""
    import time

    import pytest

    from stock_checker.yahoo_universe_discovery import fetch_yahoo_screen_symbols

    class _YF:
        @staticmethod
        def screen(screen, count=25):
            time.sleep(2.0)
            return {"quotes": []}

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _YF)
    with pytest.raises(TimeoutError, match="timed out"):
        fetch_yahoo_screen_symbols("hang_probe", count=5, timeout_sec=1)


def test_fetch_yahoo_screen_refuses_second_while_hung(monkeypatch):
    """Hung screen stays one worker — a retry must not start another spend."""
    import threading

    import pytest

    from stock_checker.yahoo_universe_discovery import fetch_yahoo_screen_symbols

    release = threading.Event()
    calls = {"n": 0}

    class _YF:
        @staticmethod
        def screen(screen, count=25):
            calls["n"] += 1
            release.wait(5)
            return {"quotes": [{"symbol": "AAPL"}]}

    monkeypatch.setitem(__import__("sys").modules, "yfinance", _YF)
    try:
        with pytest.raises(TimeoutError, match="timed out after"):
            fetch_yahoo_screen_symbols("held_screen", count=5, timeout_sec=1)
        with pytest.raises(TimeoutError, match="still in flight"):
            fetch_yahoo_screen_symbols("held_screen", count=5, timeout_sec=1)
        assert calls["n"] == 1
    finally:
        release.set()
