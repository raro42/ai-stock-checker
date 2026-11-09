"""Improve-tick freshness glance (hourly Cursor keep-alive; display only)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    IMPROVE_TICK_AGING_SEC,
    IMPROVE_TICK_FRESH_SEC,
    build_improve_tick_glance,
    improve_tick_source_speak,
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
    assert g["source_bit"] == ""
    assert g["source_escalate"] is False
    assert "fresh" in g["line"]
    assert "ok" in g["line"]
    assert "start only" not in g["line"]
    assert "log mtime" not in g["line"]
    assert g["age_sec"] == 14 * 60


def test_improve_tick_source_speak() -> None:
    assert improve_tick_source_speak("") == ("", False)
    assert improve_tick_source_speak("cursor end") == ("", False)
    assert improve_tick_source_speak("cursor start") == ("start only", True)
    assert improve_tick_source_speak("loop tick") == ("loop tick", False)
    assert improve_tick_source_speak("cursor log") == ("log mtime", True)
    assert improve_tick_source_speak("loop log") == ("log mtime", True)


def test_improve_tick_glance_start_only_speaks_and_ages(tmp_path: Path) -> None:
    """Start without end is not a finished tick — speak + escalate fresh."""
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve start\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T21:00Z")
    )
    assert g["ready"] is True
    assert g["source"] == "cursor start"
    assert g["source_bit"] == "start only"
    assert g["source_escalate"] is True
    assert g["freshness"] == "fresh"
    assert g["tone"] == "aging"
    assert "start only" in g["line"]


def test_improve_tick_glance_log_mtime_speaks_and_ages(tmp_path: Path) -> None:
    """Truncated log mtime ≠ finished end — speak + escalate fresh."""
    log = tmp_path / "run_cursor_improve.log"
    log.write_text("garbage not a tick line\n", encoding="utf-8")
    # Force mtime into the fresh window relative to fixed now.
    now = _clock("2026-11-09T21:00Z")
    os.utime(log, (now.timestamp() - 600, now.timestamp() - 600))
    g = build_improve_tick_glance(tmp_path, now=now)
    assert g["ready"] is True
    assert g["source"] == "cursor log"
    assert g["source_bit"] == "log mtime"
    assert g["source_escalate"] is True
    assert g["freshness"] == "fresh"
    assert g["tone"] == "aging"
    assert "log mtime" in g["line"]


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
    assert g["source_bit"] == "loop tick"
    assert g["source_escalate"] is False
    assert g["freshness"] == "fresh"
    assert g["tone"] == "ok"
    assert g["rc"] is None
    assert "loop tick" in g["line"]


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
