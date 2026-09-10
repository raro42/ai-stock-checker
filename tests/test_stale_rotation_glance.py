"""Stale-name rotation honesty glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_stale_rotation_glance, load_desk_snapshot
from stock_checker.exit_policy import DEFAULT_ROTATE_MIN_PROFIT_PCT


def test_stale_rotation_glance_line() -> None:
    g = build_stale_rotation_glance()
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert g["require_off_scan_list"] is True
    assert g["require_replacement"] is True
    assert g["winners_only"] is True
    assert g["rotate_min_pct"] == float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    assert "off full scan list" in g["line"]
    assert "top-N replacement" in g["line"]
    assert f"winners ≥+{float(DEFAULT_ROTATE_MIN_PROFIT_PCT):g}%" in g["line"]


def test_stale_rotation_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["stale_rotation_glance"]
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert "off full scan list" in g["line"]
    assert "replacement" in g["line"]
