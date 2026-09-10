"""Book posture modes honesty glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_book_posture_glance, load_desk_snapshot


def test_book_posture_glance_line() -> None:
    g = build_book_posture_glance()
    assert g["ready"] is True
    assert g["tone"] == "posture"
    assert g["modes"] == ("open", "at_cap", "overweight")
    assert g["overweight_scan_rotation"] is False
    assert g["overweight_new_buys"] is False
    assert "open=adds" in g["line"]
    assert "at_cap" in g["line"]
    assert "overweight=TP/SL+trim only" in g["line"]


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
    assert "overweight" in g["line"]
    assert "at_cap" in g["line"]
