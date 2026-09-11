"""Live book posture + next overweight trim glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_book_posture_glance, load_desk_snapshot


def test_book_posture_glance_open_empty() -> None:
    g = build_book_posture_glance([])
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["posture"] == "open"
    assert g["modes"] == ("open", "at_cap", "overweight")
    assert g["overweight_scan_rotation"] is False
    assert g["overweight_new_buys"] is False
    assert "live open 0/5" in g["line"]
    assert "adds OK" in g["line"]


def test_book_posture_glance_at_cap() -> None:
    rows = [
        {"symbol": f"S{i}", "held_seconds": 100_000, "unrealized_pct": 1.0}
        for i in range(5)
    ]
    g = build_book_posture_glance(rows, max_positions=5)
    assert g["posture"] == "at_cap"
    assert g["tone"] == "at_cap"
    assert "live at_cap 5/5" in g["line"]
    assert "rotate OK" in g["line"]
    assert g["trim_symbol"] == ""


def test_book_posture_glance_overweight_next_trim_winner() -> None:
    hold = 100_000.0
    rows = [
        {"symbol": "LOSER", "held_seconds": hold, "unrealized_pct": -2.0},
        {"symbol": "WEAK", "held_seconds": hold, "unrealized_pct": 1.5},
        {"symbol": "STRONG", "held_seconds": hold, "unrealized_pct": 4.0},
        {"symbol": "A", "held_seconds": hold, "unrealized_pct": 0.5},
        {"symbol": "B", "held_seconds": hold, "unrealized_pct": -1.0},
        {"symbol": "C", "held_seconds": hold, "unrealized_pct": 2.0},
    ]
    g = build_book_posture_glance(rows, max_positions=5, min_hold_hours=24)
    assert g["posture"] == "overweight"
    assert g["tone"] == "overweight"
    assert g["open_positions"] == 6
    assert g["trim_symbol"] == "A"
    assert "next trim A" in g["line"]
    assert "winner" in g["line"]


def test_book_posture_glance_overweight_trim_paused_min_hold() -> None:
    rows = [
        {"symbol": f"S{i}", "held_seconds": 60.0, "unrealized_pct": 3.0}
        for i in range(6)
    ]
    g = build_book_posture_glance(rows, max_positions=5, min_hold_hours=24)
    assert g["posture"] == "overweight"
    assert g["trim_symbol"] == ""
    assert "trim paused" in g["line"]


def test_book_posture_glance_charts_skip_trim_guess() -> None:
    rows = [{"symbol": f"S{i}", "held_seconds": 0.0} for i in range(6)]
    g = build_book_posture_glance(rows, max_positions=5, suggest_trim=False)
    assert g["posture"] == "overweight"
    assert g["trim_symbol"] == ""
    assert "TP/SL+trim only" in g["line"]
    assert "next trim" not in g["line"]


def test_book_posture_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["book_posture_glance"]
    assert g["ready"] is True
    assert g["posture"] == "open"
    assert "live open" in g["line"]


def test_book_posture_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["book_posture_glance"]
    assert g["ready"] is True
    assert g["posture"] == "open"
    assert "live open" in g["line"]
