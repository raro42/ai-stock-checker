"""Stock breakout entry-guard glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_breakout_guard_glance, load_desk_snapshot
from stock_checker.entry_guards import BREAKOUT_PCT_MAX, BREAKOUT_PCT_MIN


def test_breakout_guard_glance_ready() -> None:
    g = build_breakout_guard_glance()
    assert g["ready"] is True
    assert g["tone"] == "breakout"
    assert g["pullback_min_pct"] == float(BREAKOUT_PCT_MIN)
    assert g["pullback_max_pct"] == float(BREAKOUT_PCT_MAX)
    assert "AI BUY" in g["line"]
    assert "LOW blocked" in g["line"]
    assert "pullback" in g["line"]


def test_breakout_guard_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["breakout_guard_glance"]
    assert g["ready"] is True
    assert "breakouts" in g["line"]


def test_breakout_guard_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["breakout_guard_glance"]
    assert g["ready"] is True
    assert g["tone"] == "breakout"
    assert "AI BUY" in g["line"]
