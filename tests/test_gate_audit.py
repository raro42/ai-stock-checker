"""Offline tests for gate soft-allow audit + desk memory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_checker.gate_audit import (
    enrich_soft_allows,
    format_expired_soft_allow_tally,
    is_soft_allow_reason,
    load_soft_allows,
    log_soft_allow,
    recent_soft_allows,
    record_soft_allow,
    soft_allow_is_expired,
)


def test_is_soft_allow_reason_markers() -> None:
    assert is_soft_allow_reason("regime unknown — no SPY bars")
    assert is_soft_allow_reason("skip_no_bars")
    assert is_soft_allow_reason("insufficient history")
    assert is_soft_allow_reason("empty Yahoo earnings window · fail-open")
    assert is_soft_allow_reason("malformed Yahoo earnings · fail-open")
    assert not is_soft_allow_reason("SPY above SMA200")
    assert not is_soft_allow_reason("")


def test_record_and_recent_soft_allows(tmp_path: Path) -> None:
    record_soft_allow(tmp_path, "regime", "unknown — no bars")
    record_soft_allow(tmp_path, "rs", "hard pass — should not store")
    record_soft_allow(tmp_path, "promote", "ABC: skip_no_bars")

    events = load_soft_allows(tmp_path)
    assert len(events) == 2
    assert events[0]["gate"] == "regime"
    assert events[1]["gate"] == "promote"

    recent = recent_soft_allows(tmp_path, limit=1)
    assert len(recent) == 1
    assert recent[0]["gate"] == "promote"
    assert "skip_no_bars" in recent[0]["reason"]


def test_soft_allow_cap(tmp_path: Path) -> None:
    for i in range(5):
        record_soft_allow(tmp_path, "breadth", f"unknown #{i}", cap=3)
    events = load_soft_allows(tmp_path)
    assert len(events) == 3
    assert events[-1]["reason"] == "unknown #4"


def test_log_soft_allow_persists(tmp_path: Path, capsys) -> None:
    log_soft_allow("rs", "insufficient bars", data_dir=tmp_path)
    out = capsys.readouterr().out
    assert "Soft-allow [rs]" in out
    assert recent_soft_allows(tmp_path)


def test_soft_allow_expired_and_tally() -> None:
    """tradermonty #437: age >24h is expired; tally consolidates by gate."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert soft_allow_is_expired(stale, now=now) is True
    assert soft_allow_is_expired(fresh, now=now) is False
    assert soft_allow_is_expired("not-a-stamp", now=now) is False

    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient"},
            {"at": stale, "gate": "regime", "reason": "unknown a"},
            {"at": stale, "gate": "regime", "reason": "unknown b"},
        ],
        now=now,
    )
    assert rows[0]["expired"] is False
    assert rows[1]["expired"] is True
    assert rows[2]["expired"] is True
    assert format_expired_soft_allow_tally(rows) == "regime×2"
