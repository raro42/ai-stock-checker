"""UTC session / weekend policy glance (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

from openbb_backend.desk import build_session_glance, load_desk_snapshot


def test_session_glance_weekday_explicit() -> None:
    g = build_session_glance(weekend=False)
    assert g["ready"] is True
    assert g["tone"] == "weekday"
    assert g["weekend_mode"] is False
    assert "weekday" in g["line"]
    assert "stocks + crypto" in g["line"]


def test_session_glance_weekend_explicit() -> None:
    g = build_session_glance(weekend=True)
    assert g["ready"] is True
    assert g["tone"] == "weekend"
    assert g["weekend_mode"] is True
    assert "crypto-only" in g["line"]
    assert "stocks paused" in g["line"]


def test_session_glance_from_utc_saturday() -> None:
    sat = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)  # Saturday
    g = build_session_glance(now=sat)
    assert g["weekend_mode"] is True
    assert g["tone"] == "weekend"


def test_session_glance_from_utc_wednesday() -> None:
    wed = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)  # Wednesday
    g = build_session_glance(now=wed)
    assert g["weekend_mode"] is False
    assert g["tone"] == "weekday"


def test_session_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["session_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"weekday", "weekend"}
    assert g["weekend_mode"] is bool(snap["weekend_mode"])
    assert g["line"]
