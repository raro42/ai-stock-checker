"""No-loss-rotation policy glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_loss_rotation_glance, load_desk_snapshot
from stock_checker.exit_policy import DEFAULT_ROTATE_MIN_PROFIT_PCT


def test_loss_rotation_glance_ready() -> None:
    g = build_loss_rotation_glance()
    assert g["ready"] is True
    assert g["tone"] == "protect"
    assert g["loss_rotation"] is False
    assert g["rotate_min_pct"] == float(DEFAULT_ROTATE_MIN_PROFIT_PCT)
    assert "no loss-rotation" in g["line"]
    assert "winners" in g["line"]
    assert "overweight" in g["line"]


def test_loss_rotation_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["loss_rotation_glance"]
    assert g["ready"] is True
    assert "no loss-rotation" in g["line"]
