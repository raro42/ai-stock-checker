"""Postmortem glance (tradermonty / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    build_postmortem_glance,
    postmortem_skip_reason_lead,
    postmortem_skip_reason_lead_size,
    postmortem_skip_reason_lean,
    postmortem_skip_reason_sample_gap,
    postmortem_skip_reason_share_bands,
    postmortem_skip_reason_sides,
    postmortem_unmatched_lean_meta,
    postmortem_unmatched_vs_matched_delta,
    postmortem_unmatched_vs_matched_delta_lead,
    postmortem_unmatched_vs_matched_delta_lead_size,
    postmortem_unmatched_vs_matched_lead,
    postmortem_unmatched_vs_matched_lead_size,
    postmortem_unmatched_vs_matched_lean,
    postmortem_unmatched_vs_matched_sample_gap,
)


def test_postmortem_glance_empty() -> None:
    assert build_postmortem_glance(None)["ready"] is False
    assert build_postmortem_glance([])["ready"] is False
    assert build_postmortem_glance([{"profit_loss_pct": 1}])["ready"] is False


def test_postmortem_glance_winner() -> None:
    g = build_postmortem_glance(
        [
            {
                "symbol": "AAPL",
                "exit_reason": "take_profit",
                "held": "1.2d",
                "profit_loss_pct": 8.1,
            }
        ]
    )
    assert g["ready"] is True
    assert g["tone"] == "up"
    assert g["count"] == 1
    assert g["symbol"] == "AAPL"
    assert "Last exit · AAPL" in g["line"]
    assert "take_profit" in g["line"]
    assert "1.2d" in g["line"]
    assert "+8.1%" in g["line"]
    assert g["lean"] == ""
    assert g["lean_meta"] == "quiet"


def test_postmortem_glance_loser_with_count() -> None:
    g = build_postmortem_glance(
        [
            {
                "symbol": "EXPE",
                "exit_reason": "stop_loss",
                "held": "6h",
                "profit_loss_pct": -5.2,
            },
            {"symbol": "NTRA", "exit_reason": "rotate", "held": "2d", "profit_loss_pct": 3.0},
        ]
    )
    assert g["ready"] is True
    assert g["tone"] == "down"
    assert g["count"] == 2
    assert "EXPE" in g["line"]
    assert "2 closed" in g["line"]
    assert "NTRA" not in g["line"]
    assert g["lean"] == ""


def test_postmortem_glance_line_cap() -> None:
    g = build_postmortem_glance(
        [
            {
                "symbol": "VERYLONGSYMBOLNAME",
                "exit_reason": "take_profit_very_long_reason",
                "held": "12.5d",
                "profit_loss_pct": 12.345,
            }
            for _ in range(9)
        ]
    )
    assert g["ready"] is True
    assert len(g["line"]) <= 96
    assert g["line"].endswith("…") or len(g["line"]) < 96


def test_postmortem_glance_unmatched_skips_pnl() -> None:
    """tradermonty #689: unmatched sell speaks skipped, not invented %."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
                "profit_loss_pct": None,
            }
        ]
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["matched_count"] == 0
    assert g["unmatched_count"] == 1
    assert g["count"] == 0
    assert g["n_rounds"] == 1
    assert g["unmatched_share_pct"] == 100
    assert g["unmatched_share_severity"] == "hot"
    assert g["matched_share_pct"] == 0
    assert g["matched_share_severity"] == "thin"
    assert g["lean"] == (
        "vs 0 matched · thin · 0%"
        " · unmatched vs matched align · hot|thin"
        " · Δ wide · +100pp · lean vs Δ align · wide"
        " · Δ lead · unmatched"
    )
    assert g["lean_warn"] is True
    assert g["vs_matched_lean"] == "unmatched vs matched align · hot|thin"
    assert g["vs_matched_lean_warn"] is False
    assert g["vs_matched_delta_pp"] == 100
    assert g["vs_matched_delta_severity"] == "wide"
    assert g["vs_matched_lean_vs_delta"] == "align · wide"
    assert g["vs_matched_lean_vs_delta_warn"] is True
    assert g["vs_matched_delta_lead"] == "unmatched"
    # Sole-side — no ownership lead / Δ lead size when quieter% is 0.
    assert g["vs_matched_lead"] == ""
    assert g["vs_matched_sample_gap"] == ""
    assert g["vs_matched_lead_size"] is None
    assert g["vs_matched_delta_lead_size"] is None
    assert g["vs_matched_delta_lead_size_louder_pct"] is None
    assert g["vs_matched_delta_lead_size_quieter_pct"] is None
    assert "vs matched" in g["lean_meta"]
    assert "align" in g["lean_meta"]
    assert "Δ" in g["lean_meta"]
    assert "lead" in g["lean_meta"]
    assert "Unmatched · TSLA" in g["line"]
    assert "skipped" in g["line"]
    assert "no closed" in g["line"]
    assert "hot · 100%" in g["line"]
    # Primary clip stays short — vs matched lives under lean.
    assert "vs 0 matched" not in g["line"]
    assert g["profit_loss_pct"] is None
    assert "+%" not in g["line"] and "-%" not in g["line"]


def test_postmortem_glance_unobserved_skips_pnl() -> None:
    """tradermonty #714: missing price speaks Unobserved, not invented %."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "MSFT",
                "exit_reason": "unobserved",
                "accounting": "skipped",
                "profit_loss_pct": None,
            }
        ]
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["unmatched_count"] == 1
    assert g["orphan_unmatched_count"] == 0
    assert g["unobserved_count"] == 1
    assert g["matched_count"] == 0
    assert g["skip_reason_bit"] == "1 unobserved"
    assert "Unobserved · MSFT" in g["line"]
    assert "Unmatched ·" not in g["line"]
    assert "skipped" in g["line"]
    assert g["profit_loss_pct"] is None


def test_postmortem_skip_reason_sides_and_lead() -> None:
    """Orphan vs unobserved sides — do not call missing prices unmatched."""
    assert postmortem_skip_reason_sides(2, 0) == ("2 unmatched", 2, 0)
    assert postmortem_skip_reason_sides(0, 2) == ("2 unobserved", 0, 2)
    assert postmortem_skip_reason_sides(1, 1) == (
        "1 unmatched · 1 unobserved",
        1,
        1,
    )
    assert postmortem_skip_reason_lead(2, 1) == (
        "lead unmatched · 67%",
        "unmatched",
        67,
    )
    assert postmortem_skip_reason_lead(1, 2) == (
        "lead unobserved · 67%",
        "unobserved",
        67,
    )
    assert postmortem_skip_reason_lead(1, 1) == ("", "", None)
    assert postmortem_skip_reason_sample_gap(1, 1) == "unmatched/unobserved tied"
    assert postmortem_skip_reason_sample_gap(2, 1) == ""
    # Lead size only after a strict lead; tied / sole-side stay silent.
    assert postmortem_skip_reason_lead_size(
        2, 1, lead_name="unmatched"
    ) == (2.0, 2, 1)
    assert postmortem_skip_reason_lead_size(
        1, 2, lead_name="unobserved"
    ) == (2.0, 2, 1)
    assert postmortem_skip_reason_lead_size(1, 1, lead_name="") == (
        None,
        None,
        None,
    )
    assert postmortem_skip_reason_lead_size(
        2, 0, lead_name="unmatched"
    ) == (None, None, None)
    # Share bands + severity lean (hot|quiet of skipped).
    assert postmortem_skip_reason_share_bands(3, 1) == (
        75.0,
        "hot",
        25.0,
        "quiet",
    )
    assert postmortem_skip_reason_share_bands(2, 1) == (
        67.0,
        "hot",
        33.0,
        "",
    )
    assert postmortem_skip_reason_share_bands(1, 1) == (
        50.0,
        "hot",
        50.0,
        "hot",
    )
    assert postmortem_skip_reason_share_bands(2, 0) == (None, "", None, "")
    assert postmortem_skip_reason_lean("hot", "quiet") == (
        "unmatched vs unobserved align · hot|quiet",
        False,
    )
    assert postmortem_skip_reason_lean("quiet", "hot") == (
        "unmatched vs unobserved align · quiet|hot",
        False,
    )
    bit, warn = postmortem_skip_reason_lean("hot", "")
    assert bit == "unmatched vs unobserved clash · unmatched hot · unobserved ok"
    assert warn is True
    bit, warn = postmortem_skip_reason_lean("hot", "hot")
    assert "clash" in bit and "hot" in bit
    assert warn is True
    assert postmortem_skip_reason_lean("", "") == ("", False)


def test_postmortem_glance_two_unobserved_not_unmatched_label() -> None:
    """All-unobserved peer count speaks unobserved, not unmatched."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "MSFT",
                "exit_reason": "unobserved",
                "accounting": "skipped",
            },
            {
                "symbol": "AMD",
                "exit_reason": "unobserved",
                "accounting": "skipped",
            },
        ]
    )
    assert g["orphan_unmatched_count"] == 0
    assert g["unobserved_count"] == 2
    assert g["skip_reason_bit"] == "2 unobserved"
    assert "2 unobserved" in g["line"]
    assert "2 unmatched" not in g["line"]


def test_postmortem_glance_orphan_vs_unobserved_tied() -> None:
    """Mixed skip reasons speak sides + tied ownership."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "MSFT",
                "exit_reason": "unobserved",
                "accounting": "skipped",
            },
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
        ]
    )
    assert g["orphan_unmatched_count"] == 1
    assert g["unobserved_count"] == 1
    assert g["skip_reason_bit"] == "1 unmatched · 1 unobserved"
    assert g["skip_reason_sample_gap"] == "unmatched/unobserved tied"
    assert g["skip_reason_lead"] == ""
    assert g["skip_reason_lead_size"] is None
    assert "1 unmatched · 1 unobserved" in g["line"]
    # Primary clip uses short ``tied`` after sides; field keeps the prefix.
    assert "tied" in g["line"]
    assert "hot · 100%" in g["line"]
    assert "skip size" not in g["lean"]
    # 50/50 both hot → severity clash under lean (no lead size).
    assert g["skip_reason_lean"] == (
        "unmatched vs unobserved clash · unmatched hot · unobserved hot"
    )
    assert g["skip_reason_lean_warn"] is True
    assert "unmatched vs unobserved clash" in g["lean"]
    assert g["lean_warn"] is True


def test_postmortem_glance_orphan_vs_unobserved_lead_size() -> None:
    """Skip-reason lead size under lean — lead name/% ≠ magnitude."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "MSFT",
                "exit_reason": "unobserved",
                "accounting": "skipped",
            },
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
            {
                "symbol": "NVDA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
        ]
    )
    assert g["orphan_unmatched_count"] == 2
    assert g["unobserved_count"] == 1
    assert g["skip_reason_bit"] == "2 unmatched · 1 unobserved"
    assert g["skip_reason_lead"] == "lead unmatched · 67%"
    assert g["skip_reason_lead_name"] == "unmatched"
    assert g["skip_reason_lead_size"] == 2.0
    assert g["skip_reason_lead_size_louder"] == 2
    assert g["skip_reason_lead_size_quieter"] == 1
    # Primary keeps sides + lead; size stays under lean fold.
    assert "lead unmatched · 67%" in g["line"]
    assert "skip size" not in g["line"]
    assert "skip size · 2×" in g["lean"]
    assert "skip size sides · louder 2 · quieter 1" in g["lean"]
    assert "skip size" in g["lean_meta"]
    # 67/33 → hot vs mid clash (severity after size).
    assert g["skip_reason_orphan_share_severity"] == "hot"
    assert g["skip_reason_unobserved_share_severity"] == ""
    assert g["skip_reason_lean"] == (
        "unmatched vs unobserved clash · unmatched hot · unobserved ok"
    )
    assert g["skip_reason_lean_warn"] is True
    assert "unmatched vs unobserved clash" in g["lean"]
    assert "skip clash" in g["lean_meta"] or "clash" in g["lean_meta"]


def test_postmortem_glance_orphan_vs_unobserved_severity_align() -> None:
    """Complementary hot|quiet skip shares align under lean (no warn)."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "MSFT",
                "exit_reason": "unobserved",
                "accounting": "skipped",
            },
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
            {
                "symbol": "NVDA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
            {
                "symbol": "AMD",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
        ]
    )
    assert g["orphan_unmatched_count"] == 3
    assert g["unobserved_count"] == 1
    assert g["skip_reason_orphan_share_pct"] == 75.0
    assert g["skip_reason_unobserved_share_pct"] == 25.0
    assert g["skip_reason_orphan_share_severity"] == "hot"
    assert g["skip_reason_unobserved_share_severity"] == "quiet"
    assert g["skip_reason_lean"] == (
        "unmatched vs unobserved align · hot|quiet"
    )
    assert g["skip_reason_lean_warn"] is False
    assert "unmatched vs unobserved align · hot|quiet" in g["lean"]
    # Align is calm — fold may still warn from thin matched remainder.
    assert "skip align" in g["lean_meta"] or "align" in g["lean_meta"]


def test_postmortem_glance_matched_beside_unmatched() -> None:
    g = build_postmortem_glance(
        [
            {
                "symbol": "AAPL",
                "exit_reason": "tp",
                "held": "1d",
                "profit_loss_pct": 8.0,
            },
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
        ]
    )
    assert g["matched_count"] == 1
    assert g["unmatched_count"] == 1
    assert g["count"] == 1
    assert g["n_rounds"] == 2
    assert g["unmatched_share_pct"] == 50
    assert g["unmatched_share_severity"] == "hot"
    assert g["matched_share_pct"] == 50
    assert g["matched_share_severity"] == ""
    # 1·1 → tied (no strict lead / size); hot vs mid matched → severity clash.
    # 50−50 = 0pp → thin Δ (mid share band stays silent on severity lean only).
    assert g["lean"] == (
        "vs 1 matched · 50% · unmatched/matched tied"
        " · unmatched vs matched clash · unmatched hot · matched ok"
        " · Δ thin · 0pp · lean vs Δ align · thin"
    )
    assert g["vs_matched_lead"] == ""
    assert g["vs_matched_sample_gap"] == "unmatched/matched tied"
    assert g["vs_matched_lead_size"] is None
    assert g["vs_matched_lean"] == (
        "unmatched vs matched clash · unmatched hot · matched ok"
    )
    assert g["vs_matched_lean_warn"] is True
    assert g["vs_matched_delta_pp"] == 0
    assert g["vs_matched_delta_severity"] == "thin"
    assert g["vs_matched_lean_vs_delta"] == "align · thin"
    assert g["vs_matched_lean_vs_delta_warn"] is False
    # 0pp → no Δ lead / size (signed spread has no owner).
    assert g["vs_matched_delta_lead"] == ""
    assert g["vs_matched_delta_lead_size"] is None
    assert g["lean_warn"] is True
    assert "tied" in g["lean_meta"]
    assert "clash" in g["lean_meta"]
    assert "Δ" in g["lean_meta"]
    # Hot unmatched peers escalate a green last-exit strip.
    assert g["tone"] == "warn"
    assert "Last exit · AAPL" in g["line"]
    assert "+8.0%" in g["line"]
    assert "1 unmatched · skipped · hot · 50%" in g["line"]
    assert "vs 1 matched" not in g["line"]
    assert "tied" not in g["line"]
    assert "clash" not in g["line"]
    assert "Δ thin" not in g["line"]
    assert "Δ lead" not in g["line"]


def test_postmortem_glance_unmatched_share_quiet() -> None:
    """Quiet share when orphans are a small slice of closed rounds."""
    rows = [
        {
            "symbol": "AAPL",
            "exit_reason": "tp",
            "held": "1d",
            "profit_loss_pct": 8.0,
        }
    ]
    for i, sym in enumerate(["MSFT", "NVDA", "META", "AMZN"]):
        rows.append(
            {
                "symbol": sym,
                "exit_reason": "tp",
                "held": f"{i + 1}d",
                "profit_loss_pct": 1.0,
            }
        )
    rows.append(
        {
            "symbol": "TSLA",
            "exit_reason": "unmatched",
            "accounting": "skipped",
        }
    )
    g = build_postmortem_glance(rows)
    assert g["matched_count"] == 5
    assert g["unmatched_count"] == 1
    assert g["n_rounds"] == 6
    assert g["unmatched_share_pct"] == 17
    assert g["unmatched_share_severity"] == "quiet"
    assert g["matched_share_pct"] == 83
    assert g["matched_share_severity"] == "strong"
    assert g["lean"] == (
        "vs 5 matched · strong · 83% · lead matched · 83%"
        " · lead size · 5× · lead size sides · louder 5 · quieter 1"
        " · unmatched vs matched align · quiet|strong"
        " · Δ wide · -66pp · lean vs Δ align · wide"
        " · Δ lead · matched"
        " · Δ lead size · 4.88×"
        " · Δ lead size sides · louder 83% · quieter 17%"
    )
    assert g["vs_matched_lead"] == "lead matched · 83%"
    assert g["vs_matched_lead_name"] == "matched"
    assert g["vs_matched_lead_pct"] == 83
    assert g["vs_matched_sample_gap"] == ""
    assert g["vs_matched_lead_size"] == 5.0
    assert g["vs_matched_lead_size_louder"] == 5
    assert g["vs_matched_lead_size_quieter"] == 1
    assert g["vs_matched_lean"] == (
        "unmatched vs matched align · quiet|strong"
    )
    assert g["vs_matched_lean_warn"] is False
    assert g["vs_matched_delta_pp"] == -66
    assert g["vs_matched_delta_severity"] == "wide"
    assert g["vs_matched_lean_vs_delta"] == "align · wide"
    assert g["vs_matched_lean_vs_delta_warn"] is False
    assert g["vs_matched_delta_lead"] == "matched"
    assert g["vs_matched_delta_lead_size"] == 4.88
    assert g["vs_matched_delta_lead_size_louder_pct"] == 83
    assert g["vs_matched_delta_lead_size_quieter_pct"] == 17
    assert g["lean_warn"] is False
    assert "matched" in g["lean_meta"]
    assert "size" in g["lean_meta"]
    assert "align" in g["lean_meta"]
    assert "Δ" in g["lean_meta"]
    assert "lead" in g["lean_meta"]
    assert g["tone"] == "up"
    assert "1 unmatched · skipped · quiet · 17%" in g["line"]
    assert "vs 5 matched" not in g["line"]
    assert "lead matched" not in g["line"]
    assert "lead size" not in g["line"]
    assert "align" not in g["line"]
    assert "Δ wide" not in g["line"]
    assert "Δ lead" not in g["line"]


def test_postmortem_glance_unmatched_share_mid() -> None:
    """Mid band shows % only (not hot/quiet); tone stays on last exit."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "AAPL",
                "exit_reason": "tp",
                "held": "1d",
                "profit_loss_pct": 8.0,
            },
            {
                "symbol": "MSFT",
                "exit_reason": "tp",
                "held": "2d",
                "profit_loss_pct": 3.0,
            },
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
        ]
    )
    assert g["unmatched_count"] == 1
    assert g["n_rounds"] == 3
    assert g["unmatched_share_pct"] == 33
    assert g["unmatched_share_severity"] == ""
    assert g["matched_share_pct"] == 67
    assert g["matched_share_severity"] == ""
    assert g["lean"] == (
        "vs 2 matched · 67% · lead matched · 67%"
        " · lead size · 2× · lead size sides · louder 2 · quieter 1"
    )
    assert g["vs_matched_lead"] == "lead matched · 67%"
    assert g["vs_matched_lead_name"] == "matched"
    assert g["vs_matched_lead_pct"] == 67
    assert g["vs_matched_lead_size"] == 2.0
    assert g["vs_matched_lead_size_louder"] == 2
    assert g["vs_matched_lead_size_quieter"] == 1
    # Mid both → severity lean silent → share Δ / Δ lead / size stay silent too.
    assert g["vs_matched_lean"] == ""
    assert g["vs_matched_lean_warn"] is False
    assert g["vs_matched_delta_pp"] is None
    assert g["vs_matched_delta_severity"] == ""
    assert g["vs_matched_lean_vs_delta"] == ""
    assert g["vs_matched_delta_lead"] == ""
    assert g["vs_matched_delta_lead_size"] is None
    assert g["lean_warn"] is False
    assert g["tone"] == "up"
    assert "1 unmatched · skipped · 33%" in g["line"]
    assert "hot" not in g["line"]
    assert "quiet" not in g["line"]
    assert "vs 2 matched" not in g["line"]
    assert "lead matched" not in g["line"]
    assert "lead size" not in g["line"]


def test_postmortem_glance_unmatched_owns_roster() -> None:
    """Unmatched majority beside matched closes → lead unmatched under lean."""
    g = build_postmortem_glance(
        [
            {
                "symbol": "AAPL",
                "exit_reason": "tp",
                "held": "1d",
                "profit_loss_pct": 8.0,
            },
            {
                "symbol": "TSLA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
            {
                "symbol": "NVDA",
                "exit_reason": "unmatched",
                "accounting": "skipped",
            },
        ]
    )
    assert g["matched_count"] == 1
    assert g["unmatched_count"] == 2
    assert g["n_rounds"] == 3
    assert g["unmatched_share_pct"] == 67
    assert g["unmatched_share_severity"] == "hot"
    assert g["matched_share_pct"] == 33
    assert g["matched_share_severity"] == "thin"
    assert g["lean"] == (
        "vs 1 matched · thin · 33% · lead unmatched · 67%"
        " · lead size · 2× · lead size sides · louder 2 · quieter 1"
        " · unmatched vs matched align · hot|thin"
        " · Δ wide · +34pp · lean vs Δ align · wide"
        " · Δ lead · unmatched"
        " · Δ lead size · 2.03×"
        " · Δ lead size sides · louder 67% · quieter 33%"
    )
    assert g["vs_matched_lead"] == "lead unmatched · 67%"
    assert g["vs_matched_lead_name"] == "unmatched"
    assert g["vs_matched_lead_pct"] == 67
    assert g["vs_matched_lead_size"] == 2.0
    assert g["vs_matched_lead_size_louder"] == 2
    assert g["vs_matched_lead_size_quieter"] == 1
    assert g["vs_matched_lean"] == "unmatched vs matched align · hot|thin"
    assert g["vs_matched_lean_warn"] is False
    assert g["vs_matched_delta_pp"] == 34
    assert g["vs_matched_delta_severity"] == "wide"
    assert g["vs_matched_lean_vs_delta"] == "align · wide"
    assert g["vs_matched_lean_vs_delta_warn"] is True
    assert g["vs_matched_delta_lead"] == "unmatched"
    assert g["vs_matched_delta_lead_size"] == 2.03
    assert g["vs_matched_delta_lead_size_louder_pct"] == 67
    assert g["vs_matched_delta_lead_size_quieter_pct"] == 33
    assert g["lean_warn"] is True
    assert "unmatched" in g["lean_meta"]
    assert "size" in g["lean_meta"]
    assert "align" in g["lean_meta"]
    assert "Δ" in g["lean_meta"]
    assert "lead" in g["lean_meta"]
    assert g["tone"] == "warn"
    assert "lead unmatched" not in g["line"]
    assert "lead size" not in g["line"]
    assert "align" not in g["line"]
    assert "Δ wide" not in g["line"]
    assert "Δ lead" not in g["line"]


def test_postmortem_unmatched_vs_matched_lead_helpers() -> None:
    bit, name, pct = postmortem_unmatched_vs_matched_lead(2, 3)
    assert bit == "lead matched · 60%"
    assert name == "matched"
    assert pct == 60
    bit, name, pct = postmortem_unmatched_vs_matched_lead(3, 2)
    assert bit == "lead unmatched · 60%"
    assert name == "unmatched"
    assert pct == 60
    assert postmortem_unmatched_vs_matched_lead(2, 2) == ("", "", None)
    assert postmortem_unmatched_vs_matched_lead(2, 0) == ("", "", None)
    assert postmortem_unmatched_vs_matched_sample_gap(1, 1) == (
        "unmatched/matched tied"
    )
    assert postmortem_unmatched_vs_matched_sample_gap(2, 1) == ""
    assert postmortem_unmatched_vs_matched_sample_gap(2, 0) == ""
    assert postmortem_unmatched_vs_matched_lead_size(
        2, 1, lead_name="unmatched"
    ) == (2.0, 2, 1)
    assert postmortem_unmatched_vs_matched_lead_size(
        5, 1, lead_name="matched"
    ) == (5.0, 5, 1)
    assert postmortem_unmatched_vs_matched_lead_size(
        3, 2, lead_name="unmatched"
    ) == (1.5, 3, 2)
    assert postmortem_unmatched_vs_matched_lead_size(
        2, 2, lead_name=""
    ) == (None, None, None)
    assert postmortem_unmatched_vs_matched_lead_size(
        2, 0, lead_name="unmatched"
    ) == (None, None, None)


def test_postmortem_unmatched_vs_matched_lean_helpers() -> None:
    bit, warn = postmortem_unmatched_vs_matched_lean("hot", "thin")
    assert bit == "unmatched vs matched align · hot|thin"
    assert warn is False
    bit, warn = postmortem_unmatched_vs_matched_lean("quiet", "strong")
    assert bit == "unmatched vs matched align · quiet|strong"
    assert warn is False
    bit, warn = postmortem_unmatched_vs_matched_lean("hot", "strong")
    assert bit == (
        "unmatched vs matched clash · unmatched hot · matched strong"
    )
    assert warn is True
    bit, warn = postmortem_unmatched_vs_matched_lean("hot", "")
    assert bit == (
        "unmatched vs matched clash · unmatched hot · matched ok"
    )
    assert warn is True
    bit, warn = postmortem_unmatched_vs_matched_lean("quiet", "")
    assert bit == (
        "unmatched vs matched clash · unmatched quiet · matched ok"
    )
    assert warn is False
    assert postmortem_unmatched_vs_matched_lean("", "") == ("", False)
    assert postmortem_unmatched_vs_matched_lean("ok", "ok") == ("", False)


def test_postmortem_unmatched_vs_matched_delta_helpers() -> None:
    """Wide / thin / mid + adverse hot|thin warn for unmatched vs matched Δ."""
    lean = "unmatched vs matched align · hot|thin"
    pp, sev, lvd, warn = postmortem_unmatched_vs_matched_delta(
        67, 33, lean_bit=lean
    )
    assert pp == 34
    assert sev == "wide"
    assert lvd == "align · wide"
    assert warn is True
    assert (
        postmortem_unmatched_vs_matched_delta_lead(pp, sev, lean_vs_delta=lvd)
        == "unmatched"
    )
    pp, sev, lvd, warn = postmortem_unmatched_vs_matched_delta(
        55, 45, lean_bit=lean
    )
    assert pp == 10
    assert sev == ""
    assert lvd == "clash · lean · Δ mid"
    assert warn is True
    assert (
        postmortem_unmatched_vs_matched_delta_lead(pp, sev, lean_vs_delta=lvd)
        == ""
    )
    pp, sev, lvd, warn = postmortem_unmatched_vs_matched_delta(
        52, 48, lean_bit=lean
    )
    assert pp == 4
    assert sev == "thin"
    assert lvd == "align · thin"
    assert warn is False
    assert (
        postmortem_unmatched_vs_matched_delta_lead(pp, sev, lean_vs_delta=lvd)
        == "unmatched"
    )
    calm = "unmatched vs matched align · quiet|strong"
    pp, sev, lvd, warn = postmortem_unmatched_vs_matched_delta(
        20, 80, lean_bit=calm
    )
    assert pp == -60
    assert sev == "wide"
    assert lvd == "align · wide"
    assert warn is False
    assert (
        postmortem_unmatched_vs_matched_delta_lead(pp, sev, lean_vs_delta=lvd)
        == "matched"
    )
    size, louder, quieter = postmortem_unmatched_vs_matched_delta_lead_size(
        20, 80, delta_lead="matched"
    )
    assert size == 4.0
    assert louder == 80
    assert quieter == 20
    assert postmortem_unmatched_vs_matched_delta_lead_size(
        100, 0, delta_lead="unmatched"
    ) == (None, None, None)
    assert postmortem_unmatched_vs_matched_delta_lead_size(
        67, 33, delta_lead=""
    ) == (None, None, None)
    assert postmortem_unmatched_vs_matched_delta(75, 25, lean_bit="") == (
        None,
        "",
        "",
        False,
    )
    assert postmortem_unmatched_vs_matched_delta(
        None, 25, lean_bit=lean
    ) == (None, "", "", False)
    assert (
        postmortem_unmatched_vs_matched_delta_lead(
            0, "thin", lean_vs_delta="align · thin"
        )
        == ""
    )


def test_postmortem_unmatched_lean_meta() -> None:
    assert postmortem_unmatched_lean_meta("") == "quiet"
    quiet = postmortem_unmatched_lean_meta(
        "vs 5 matched · strong · 83% · lead matched · 83%"
        " · lead size · 5× · lead size sides · louder 5 · quieter 1"
        " · unmatched vs matched align · quiet|strong"
        " · Δ wide · -66pp · lean vs Δ align · wide"
        " · Δ lead · matched"
        " · Δ lead size · 4.88×"
        " · Δ lead size sides · louder 83% · quieter 17%"
    )
    assert quiet.startswith("quiet")
    assert "vs matched" in quiet
    assert "matched" in quiet
    assert "size" in quiet
    assert "align" in quiet
    assert "Δ" in quiet
    assert "lead" in quiet
    warn = postmortem_unmatched_lean_meta(
        "vs 0 matched · thin · 0%"
        " · unmatched vs matched align · hot|thin"
        " · Δ wide · +100pp · lean vs Δ align · wide"
        " · Δ lead · unmatched",
        warn=True,
    )
    assert warn.startswith("warn")
    assert "vs matched" in warn
    assert "lead" in warn
    tied = postmortem_unmatched_lean_meta(
        "vs 1 matched · 50% · unmatched/matched tied"
        " · unmatched vs matched clash · unmatched hot · matched ok"
    )
    assert "tied" in tied
    assert "clash" in tied
