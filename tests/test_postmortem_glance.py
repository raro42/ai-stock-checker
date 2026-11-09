"""Postmortem glance (tradermonty / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    build_postmortem_glance,
    postmortem_unmatched_lean_meta,
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
    assert g["lean"] == "vs 0 matched · thin · 0%"
    assert g["lean_warn"] is True
    assert "vs matched" in g["lean_meta"]
    assert "Unmatched · TSLA" in g["line"]
    assert "skipped" in g["line"]
    assert "no closed" in g["line"]
    assert "hot · 100%" in g["line"]
    # Primary clip stays short — vs matched lives under lean.
    assert "vs 0 matched" not in g["line"]
    assert g["profit_loss_pct"] is None
    assert "+%" not in g["line"] and "-%" not in g["line"]


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
    assert g["lean"] == "vs 1 matched · 50%"
    assert g["lean_warn"] is False
    # Hot unmatched peers escalate a green last-exit strip.
    assert g["tone"] == "warn"
    assert "Last exit · AAPL" in g["line"]
    assert "+8.0%" in g["line"]
    assert "1 unmatched · skipped · hot · 50%" in g["line"]
    assert "vs 1 matched" not in g["line"]


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
    assert g["lean"] == "vs 5 matched · strong · 83%"
    assert g["lean_warn"] is False
    assert g["tone"] == "up"
    assert "1 unmatched · skipped · quiet · 17%" in g["line"]
    assert "vs 5 matched" not in g["line"]


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
    assert g["lean"] == "vs 2 matched · 67%"
    assert g["lean_warn"] is False
    assert g["tone"] == "up"
    assert "1 unmatched · skipped · 33%" in g["line"]
    assert "hot" not in g["line"]
    assert "quiet" not in g["line"]
    assert "vs 2 matched" not in g["line"]


def test_postmortem_unmatched_lean_meta() -> None:
    assert postmortem_unmatched_lean_meta("") == "quiet"
    quiet = postmortem_unmatched_lean_meta("vs 5 matched · strong · 83%")
    assert quiet.startswith("quiet")
    assert "vs matched" in quiet
    warn = postmortem_unmatched_lean_meta(
        "vs 0 matched · thin · 0%", warn=True
    )
    assert warn.startswith("warn")
    assert "vs matched" in warn
