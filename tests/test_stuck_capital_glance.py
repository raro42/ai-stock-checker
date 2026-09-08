"""Stuck-capital glance (A15 / portfolio AI; display only)."""

from __future__ import annotations

from openbb_backend.desk import build_stuck_capital_glance


def test_stuck_capital_glance_empty() -> None:
    assert build_stuck_capital_glance(None)["ready"] is False
    assert build_stuck_capital_glance([])["ready"] is False
    assert build_stuck_capital_glance([{"unrealized_pct": -1}])["ready"] is False


def test_stuck_capital_glance_one() -> None:
    g = build_stuck_capital_glance(
        [{"symbol": "EXPE", "unrealized_pct": -3.2, "held": "1.2d"}]
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["count"] == 1
    assert g["symbols"] == ["EXPE"]
    assert "1 past min-hold underwater" in g["line"]
    assert "EXPE -3.2%" in g["line"]


def test_stuck_capital_glance_truncates_extra() -> None:
    stuck = [
        {"symbol": f"S{i}", "unrealized_pct": -1.0 * (i + 1)} for i in range(5)
    ]
    g = build_stuck_capital_glance(stuck)
    assert g["ready"] is True
    assert g["count"] == 5
    assert "S0 -1.0%" in g["line"]
    assert "S1 -2.0%" in g["line"]
    assert "S2 -3.0%" in g["line"]
    assert "+2 more" in g["line"]
    assert "S3" not in g["line"]
    assert len(g["line"]) <= 96


def test_stuck_capital_glance_line_cap() -> None:
    stuck = [
        {
            "symbol": "VERYLONGSYMBOLNAME",
            "unrealized_pct": -12.345,
        }
        for _ in range(4)
    ]
    g = build_stuck_capital_glance(stuck)
    assert g["ready"] is True
    assert len(g["line"]) <= 96
    assert g["line"].endswith("…") or len(g["line"]) < 96
