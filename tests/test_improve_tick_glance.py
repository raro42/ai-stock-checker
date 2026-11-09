"""Improve-tick freshness glance (hourly Cursor keep-alive; display only)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    IMPROVE_TICK_AGING_SEC,
    IMPROVE_TICK_FRESH_SEC,
    build_improve_tick_glance,
    load_desk_snapshot,
)


def _clock(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def test_improve_tick_glance_empty(tmp_path: Path) -> None:
    assert build_improve_tick_glance(None)["ready"] is False
    assert build_improve_tick_glance(tmp_path)["ready"] is False


def test_improve_tick_glance_fresh_ok(tmp_path: Path) -> None:
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:40Z cursor improve start\n"
        "2026-11-09T20:46Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T21:00Z")
    )
    assert g["ready"] is True
    assert g["tone"] == "ok"
    assert g["freshness"] == "fresh"
    assert g["failed"] is False
    assert g["rc"] == 0
    assert g["source"] == "cursor end"
    assert "fresh" in g["line"]
    assert "ok" in g["line"]
    assert g["age_sec"] == 14 * 60


def test_improve_tick_glance_aging(tmp_path: Path) -> None:
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T18:00Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T20:00Z")
    )
    assert g["ready"] is True
    assert g["freshness"] == "aging"
    assert g["tone"] == "aging"
    assert IMPROVE_TICK_FRESH_SEC < g["age_sec"] < IMPROVE_TICK_AGING_SEC


def test_improve_tick_glance_stale_and_failed_rc(tmp_path: Path) -> None:
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T12:00Z cursor improve end rc=1\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T20:00Z")
    )
    assert g["ready"] is True
    assert g["freshness"] == "stale"
    assert g["tone"] == "warn"
    assert g["failed"] is True
    assert g["rc"] == 1
    assert "rc=1" in g["line"]
    assert g["age_sec"] >= IMPROVE_TICK_AGING_SEC


def test_improve_tick_glance_loop_tick_fallback(tmp_path: Path) -> None:
    (tmp_path / "run_improve_loop.log").write_text(
        '2026-11-09T20:46Z AGENT_LOOP_TICK_improve {"prompt": "x"}\n',
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T21:00Z")
    )
    assert g["ready"] is True
    assert g["source"] == "loop tick"
    assert g["freshness"] == "fresh"
    assert g["rc"] is None


def test_improve_tick_glance_vs_scan_clash(tmp_path: Path) -> None:
    """Fresh improve ≠ stale scan archive → clash (LAYA/soft-allow parity)."""
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path,
        now=_clock("2026-11-09T21:00Z"),
        scan_time="2026-11-09T12:00:00+00:00",
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "stale"
    assert g["scan_clash"] == "clash · scan stale"
    assert "clash · scan stale" in g["line"]
    assert g["tone"] == "warn"


def test_improve_tick_glance_vs_scan_same_band_silent(tmp_path: Path) -> None:
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path,
        now=_clock("2026-11-09T21:00Z"),
        scan_time="2026-11-09T20:50:00+00:00",
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_clash"] == ""
    assert "clash" not in g["line"]
    assert g["tone"] == "ok"


def test_improve_tick_glance_in_snapshot(tmp_path: Path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["improve_tick_glance"]
    assert g["ready"] is True
    assert g["freshness"] in {"fresh", "aging", "stale"}


def test_improve_tick_glance_in_chart_payload(tmp_path: Path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = load_chart_payload(tmp_path)["improve_tick_glance"]
    assert g["ready"] is True
    assert "fresh" in g["line"] or "aging" in g["line"] or "stale" in g["line"]
