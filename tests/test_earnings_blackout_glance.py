"""Stock earnings blackout policy glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_earnings_blackout_glance, load_desk_snapshot


def test_earnings_blackout_glance_window() -> None:
    g = build_earnings_blackout_glance()
    assert g["ready"] is True
    assert g["tone"] == "stock"
    assert g["days_before"] == 2.0
    assert g["days_after"] == 1.0
    assert "2d before" in g["line"]
    assert "1d after" in g["line"]
    assert "crypto exempt" in g["line"]


def test_earnings_blackout_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["earnings_blackout_glance"]
    assert g["ready"] is True
    assert "blackout" in g["line"]
