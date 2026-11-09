"""Postmortem glance (tradermonty / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import build_postmortem_glance


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
    assert "Unmatched · TSLA" in g["line"]
    assert "skipped" in g["line"]
    assert "no closed" in g["line"]
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
    assert g["tone"] == "up"
    assert "Last exit · AAPL" in g["line"]
    assert "+8.0%" in g["line"]
    assert "1 unmatched · skipped" in g["line"]
