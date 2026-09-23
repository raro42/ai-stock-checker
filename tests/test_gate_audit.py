"""Offline tests for gate soft-allow audit + desk memory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_checker.gate_audit import (
    enrich_soft_allows,
    format_aging_soft_allow_tally,
    format_expired_soft_allow_tally,
    is_soft_allow_reason,
    load_soft_allows,
    log_soft_allow,
    recent_soft_allows,
    record_soft_allow,
    soft_allow_event_key,
    soft_allow_freshness,
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


def test_soft_allow_rejects_duplicate_gate_reason(tmp_path: Path) -> None:
    """tradermonty #447: same gate+reason refreshes stamp; no duplicate rows."""
    assert soft_allow_event_key("Regime", "Unknown — no bars") == soft_allow_event_key(
        "regime", "unknown — no bars"
    )
    record_soft_allow(tmp_path, "regime", "unknown — no bars")
    record_soft_allow(tmp_path, "rs", "insufficient history")
    first = load_soft_allows(tmp_path)
    assert len(first) == 2
    stamp0 = first[0]["at"]
    record_soft_allow(tmp_path, "REGIME", "Unknown — no bars")
    events = load_soft_allows(tmp_path)
    assert len(events) == 2
    assert events[0]["gate"] == "rs"
    assert events[1]["gate"] == "REGIME"
    assert events[1]["reason"] == "Unknown — no bars"
    assert events[1]["at"] >= stamp0
    # Distinct reason still accumulates under the same gate.
    record_soft_allow(tmp_path, "regime", "unknown — empty Yahoo earnings window")
    assert len(load_soft_allows(tmp_path)) == 3


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
    assert rows[0]["freshness"] == "fresh"
    assert rows[1]["expired"] is True
    assert rows[1]["freshness"] == "expired"
    assert rows[2]["expired"] is True
    assert format_expired_soft_allow_tally(rows) == "regime×2"


def test_soft_allow_freshness_aging_band() -> None:
    """xang1234 / RyanJHamby: aging between 12h and 24h before expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert soft_allow_freshness(fresh, now=now) == "fresh"
    assert soft_allow_freshness(aging, now=now) == "aging"
    assert soft_allow_freshness(stale, now=now) == "expired"
    assert soft_allow_freshness("bad", now=now) == "unknown"
    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": stale, "gate": "regime", "reason": "unknown"},
        ],
        now=now,
    )
    assert [r["freshness"] for r in rows] == ["fresh", "aging", "expired"]
    assert rows[1]["expired"] is False
    assert rows[2]["expired"] is True
    assert format_aging_soft_allow_tally(rows) == "breadth×1"


def test_soft_allow_aging_tally_consolidates() -> None:
    """portfolio AI + xang1234: aging gate tally mirrors expired speak-both-sides."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = enrich_soft_allows(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert all(r["freshness"] == "aging" for r in rows)
    assert format_aging_soft_allow_tally(rows) == "breadth×2 · rs×1"
    assert format_expired_soft_allow_tally(rows) == ""
