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
    improve_tick_fresher_vs_status_age_bits,
    improve_tick_lean_meta,
    improve_tick_source_speak,
    improve_tick_source_vs_scan_bits,
    improve_tick_status_age_vs_scan_bits,
    improve_tick_status_vs_age_bits,
    improve_tick_vs_scan_fresher_bits,
    improve_tick_vs_scan_fresher_gap_sides_bits,
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


def test_improve_tick_status_vs_age_bits() -> None:
    assert improve_tick_status_vs_age_bits(
        failed=False, rc=None, freshness="stale"
    ) == ("", False)
    assert improve_tick_status_vs_age_bits(
        failed=False, rc=0, freshness="fresh"
    ) == ("", False)
    assert improve_tick_status_vs_age_bits(
        failed=False, rc=0, freshness="aging"
    ) == ("", False)
    assert improve_tick_status_vs_age_bits(
        failed=False, rc=0, freshness="stale"
    ) == ("status/age clash · ok · stale", True)
    assert improve_tick_status_vs_age_bits(
        failed=True, rc=1, freshness="fresh"
    ) == ("status/age clash · fail · fresh", True)
    assert improve_tick_status_vs_age_bits(
        failed=True, rc=1, freshness="stale"
    ) == ("status/age align · fail · stale", False)


def test_improve_tick_status_age_vs_scan_bits() -> None:
    assert improve_tick_status_age_vs_scan_bits("", "clash · scan stale") == (
        "",
        False,
    )
    assert improve_tick_status_age_vs_scan_bits(
        "status/age clash · ok · stale", ""
    ) == ("", False)
    assert improve_tick_status_age_vs_scan_bits(
        "status/age clash · ok · stale", "clash · scan fresh"
    ) == ("status/age vs scan align · clash", False)
    assert improve_tick_status_age_vs_scan_bits(
        "status/age clash · fail · fresh", "clash · scan stale"
    ) == ("status/age vs scan align · clash", False)
    assert improve_tick_status_age_vs_scan_bits(
        "status/age align · fail · stale", "clash · scan fresh"
    ) == ("clash · status/age align · scan fresh", True)


def test_improve_tick_source_vs_scan_bits() -> None:
    assert improve_tick_source_vs_scan_bits("", "clash · scan stale") == (
        "",
        False,
    )
    assert improve_tick_source_vs_scan_bits(
        "start only", "", source_escalate=True
    ) == ("", False)
    assert improve_tick_source_vs_scan_bits(
        "start only", "clash · scan stale", source_escalate=True
    ) == ("source vs scan align · clash", False)
    assert improve_tick_source_vs_scan_bits(
        "log mtime", "clash · scan fresh", source_escalate=True
    ) == ("source vs scan align · clash", False)
    assert improve_tick_source_vs_scan_bits(
        "loop tick", "clash · scan stale", source_escalate=False
    ) == ("clash · source loop tick · scan stale", True)


def test_improve_tick_vs_scan_fresher_bits() -> None:
    assert improve_tick_vs_scan_fresher_bits("fresh", "stale", "") == (
        "",
        False,
    )
    assert improve_tick_vs_scan_fresher_bits(
        "fresh", "fresh", "clash · scan fresh"
    ) == ("", False)
    assert improve_tick_vs_scan_fresher_bits(
        "fresh", "stale", "clash · scan stale"
    ) == ("fresher improve · gap wide", False)
    assert improve_tick_vs_scan_fresher_bits(
        "fresh", "aging", "clash · scan aging"
    ) == ("fresher improve · gap thin", False)
    assert improve_tick_vs_scan_fresher_bits(
        "stale", "fresh", "clash · scan fresh"
    ) == ("fresher scan · gap wide", True)
    assert improve_tick_vs_scan_fresher_bits(
        "aging", "fresh", "clash · scan fresh"
    ) == ("fresher scan · gap thin", True)


def test_improve_tick_vs_scan_fresher_gap_sides_bits() -> None:
    assert improve_tick_vs_scan_fresher_gap_sides_bits(
        "fresh", "stale", ""
    ) == ("", False)
    assert improve_tick_vs_scan_fresher_gap_sides_bits(
        "fresh", "unknown", "fresher improve · gap wide"
    ) == ("", False)
    assert improve_tick_vs_scan_fresher_gap_sides_bits(
        "fresh", "stale", "fresher improve · gap wide"
    ) == ("gap sides · improve fresh · scan stale", False)
    assert improve_tick_vs_scan_fresher_gap_sides_bits(
        "aging", "fresh", "fresher scan · gap thin"
    ) == ("gap sides · improve aging · scan fresh", False)


def test_improve_tick_fresher_vs_status_age_bits() -> None:
    assert improve_tick_fresher_vs_status_age_bits(
        "", "status/age clash · ok · stale"
    ) == ("", False)
    assert improve_tick_fresher_vs_status_age_bits(
        "fresher scan · gap wide", ""
    ) == ("", False)
    assert improve_tick_fresher_vs_status_age_bits(
        "fresher scan · gap wide", "status/age clash · ok · stale"
    ) == ("fresher vs status/age align", False)
    assert improve_tick_fresher_vs_status_age_bits(
        "fresher scan · gap wide", "status/age align · fail · stale"
    ) == ("fresher vs status/age align", False)
    assert improve_tick_fresher_vs_status_age_bits(
        "fresher improve · gap thin", "status/age clash · fail · fresh"
    ) == ("fresher vs status/age align", False)
    assert improve_tick_fresher_vs_status_age_bits(
        "fresher improve · gap wide", "status/age clash · ok · stale"
    ) == ("fresher vs status/age clash · fresher improve · stale", True)
    assert improve_tick_fresher_vs_status_age_bits(
        "fresher scan · gap thin", "status/age clash · fail · fresh"
    ) == ("fresher vs status/age clash · fresher scan · fresh", True)


def test_improve_tick_lean_meta() -> None:
    assert improve_tick_lean_meta("") == "quiet"
    assert (
        improve_tick_lean_meta("status/age vs scan align · clash")
        == "quiet · status/age vs scan"
    )
    assert (
        improve_tick_lean_meta(
            "clash · status/age align · scan fresh", warn=True
        )
        == "warn · status/age vs scan"
    )
    assert (
        improve_tick_lean_meta("source vs scan align · clash")
        == "quiet · source vs scan"
    )
    assert (
        improve_tick_lean_meta(
            "clash · source loop tick · scan stale", warn=True
        )
        == "warn · source vs scan"
    )
    assert (
        improve_tick_lean_meta("fresher improve · gap wide")
        == "quiet · fresher"
    )
    assert (
        improve_tick_lean_meta(
            "fresher improve · gap wide · gap sides · improve fresh · scan stale"
        )
        == "quiet · fresher · gap sides"
    )
    assert (
        improve_tick_lean_meta(
            "status/age vs scan align · clash · fresher scan · gap wide"
            " · gap sides · improve stale · scan fresh"
            " · fresher vs status/age align",
            warn=True,
        )
        == "warn · fresher vs status/age · status/age vs scan · fresher · gap sides"
    )
    assert (
        improve_tick_lean_meta("fresher vs status/age align")
        == "quiet · fresher vs status/age"
    )


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
    assert g["status_age_bit"] == ""
    assert IMPROVE_TICK_FRESH_SEC < g["age_sec"] < IMPROVE_TICK_AGING_SEC


def test_improve_tick_glance_ok_stale_status_age_clash(tmp_path: Path) -> None:
    """Success label beside stale age must speak clash (edge/conf parity)."""
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T12:00Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T20:00Z")
    )
    assert g["ready"] is True
    assert g["freshness"] == "stale"
    assert g["failed"] is False
    assert g["rc"] == 0
    assert g["status_age_bit"] == "status/age clash · ok · stale"
    assert g["status_age_escalate"] is True
    assert "status/age clash · ok · stale" in g["line"]
    assert g["tone"] == "warn"
    assert g["age_sec"] >= IMPROVE_TICK_AGING_SEC


def test_improve_tick_glance_fail_fresh_status_age_clash(tmp_path: Path) -> None:
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve end rc=1\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path, now=_clock("2026-11-09T21:00Z")
    )
    assert g["ready"] is True
    assert g["freshness"] == "fresh"
    assert g["failed"] is True
    assert g["status_age_bit"] == "status/age clash · fail · fresh"
    assert g["status_age_escalate"] is True
    assert "status/age clash · fail · fresh" in g["line"]
    assert g["tone"] == "warn"


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
    assert g["status_age_bit"] == "status/age align · fail · stale"
    assert g["status_age_escalate"] is False
    assert "status/age align · fail · stale" in g["line"]
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
    # Happy ok+fresh has no status/age bit → lean still names fresher/gap + sides.
    assert g["status_age_bit"] == ""
    assert g["lean"] == (
        "fresher improve · gap wide"
        " · gap sides · improve fresh · scan stale"
    )
    assert g["lean_warn"] is False
    assert g["lean_meta"] == "quiet · fresher · gap sides"
    assert "fresher" not in g["line"]
    assert "gap sides" not in g["line"]


def test_improve_tick_glance_status_age_vs_scan_align_clash(
    tmp_path: Path,
) -> None:
    """ok·stale + scan clash → lean confirms both meters disagree."""
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T12:00Z cursor improve end rc=0\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path,
        now=_clock("2026-11-09T20:00Z"),
        scan_time="2026-11-09T19:50:00+00:00",
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["freshness"] == "stale"
    assert g["status_age_bit"] == "status/age clash · ok · stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_clash"] == "clash · scan fresh"
    assert g["lean"] == (
        "status/age vs scan align · clash · fresher scan · gap wide"
        " · gap sides · improve stale · scan fresh"
        " · fresher vs status/age align"
    )
    assert g["lean_warn"] is True
    assert g["lean_meta"] == (
        "warn · fresher vs status/age · status/age vs scan · fresher · gap sides"
    )
    # Lean stays off the primary clip.
    assert "status/age vs scan" not in g["line"]
    assert "fresher" not in g["line"]
    assert "gap sides" not in g["line"]


def test_improve_tick_glance_status_age_align_vs_scan_clash(
    tmp_path: Path,
) -> None:
    """fail·stale align + scan clash → lean warns moods disagree."""
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T12:00Z cursor improve end rc=1\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path,
        now=_clock("2026-11-09T20:00Z"),
        scan_time="2026-11-09T19:50:00+00:00",
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["freshness"] == "stale"
    assert g["status_age_bit"] == "status/age align · fail · stale"
    assert g["scan_clash"] == "clash · scan fresh"
    assert g["lean"] == (
        "clash · status/age align · scan fresh · fresher scan · gap wide"
        " · gap sides · improve stale · scan fresh"
        " · fresher vs status/age align"
    )
    assert g["lean_warn"] is True
    assert g["lean_meta"] == (
        "warn · fresher vs status/age · status/age vs scan · fresher · gap sides"
    )
    assert "status/age vs scan" not in g["line"]
    assert "clash · status/age align" not in g["line"]
    assert "fresher" not in g["line"]
    assert "gap sides" not in g["line"]


def test_improve_tick_glance_source_vs_scan_align_clash(
    tmp_path: Path,
) -> None:
    """start-only + scan clash → lean confirms both meters disagree."""
    (tmp_path / "run_cursor_improve.log").write_text(
        "2026-11-09T20:46Z cursor improve start\n",
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path,
        now=_clock("2026-11-09T21:00Z"),
        scan_time="2026-11-09T12:00:00+00:00",
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["source_bit"] == "start only"
    assert g["source_escalate"] is True
    assert g["scan_clash"] == "clash · scan stale"
    assert g["lean"] == (
        "source vs scan align · clash · fresher improve · gap wide"
        " · gap sides · improve fresh · scan stale"
    )
    assert g["lean_warn"] is False
    assert g["lean_meta"] == "quiet · source vs scan · fresher · gap sides"
    assert "source vs scan" not in g["line"]
    assert "fresher" not in g["line"]
    assert "gap sides" not in g["line"]
    assert "start only" in g["line"]
    assert "clash · scan stale" in g["line"]


def test_improve_tick_glance_loop_tick_vs_scan_clash(tmp_path: Path) -> None:
    """Calm loop-tick source + scan clash → lean warns moods disagree."""
    (tmp_path / "run_improve_loop.log").write_text(
        '2026-11-09T20:46Z AGENT_LOOP_TICK_improve {"prompt": "x"}\n',
        encoding="utf-8",
    )
    g = build_improve_tick_glance(
        tmp_path,
        now=_clock("2026-11-09T21:00Z"),
        scan_time="2026-11-09T12:00:00+00:00",
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["source_bit"] == "loop tick"
    assert g["source_escalate"] is False
    assert g["scan_clash"] == "clash · scan stale"
    assert g["lean"] == (
        "clash · source loop tick · scan stale · fresher improve · gap wide"
        " · gap sides · improve fresh · scan stale"
    )
    assert g["lean_warn"] is True
    assert g["lean_meta"] == "warn · source vs scan · fresher · gap sides"
    assert "clash · source loop tick" not in g["line"]
    assert "fresher" not in g["line"]
    assert "gap sides" not in g["line"]
    assert "loop tick" in g["line"]


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
    assert g["lean"] == ""


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
