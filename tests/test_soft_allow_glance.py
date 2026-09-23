"""Fail-open soft-allow glance (display only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from openbb_backend.desk import build_soft_allow_glance


def test_soft_allow_glance_empty() -> None:
    assert build_soft_allow_glance(None)["ready"] is False
    assert build_soft_allow_glance([])["ready"] is False


def test_soft_allow_glance_one() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-09-23T11:00:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            }
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["count"] == 1
    assert g["fresh_count"] == 1
    assert g["expired_count"] == 0
    assert g["last_gate"] == "regime"
    assert "1 recent soft-allow" in g["line"]
    assert "[regime]" in g["line"]
    assert "no SPY bars" in g["line"]


def test_soft_allow_glance_truncates_reason() -> None:
    long = "x" * 100
    g = build_soft_allow_glance([{"at": "t", "gate": "rs", "reason": long}])
    assert g["ready"] is True
    assert g["last_reason"].endswith("…")
    assert len(g["last_reason"]) <= 72


def test_soft_allow_glance_consolidates_expired() -> None:
    """tradermonty #437: expired soft-allows speak count + gate tally."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": stale, "gate": "regime", "reason": "unknown — no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "unknown — no BTC bars"},
        ],
        now=now,
        fresh_hours=24.0,
    )
    assert g["count"] == 3
    assert g["fresh_count"] == 1
    assert g["expired_count"] == 2
    assert g["expired_tally"] == "regime×2"
    assert "3 soft-allows" in g["line"]
    assert "2 expired" in g["line"]
    assert "regime×2" in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_all_expired() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
            {"at": stale, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["expired_count"] == 2
    assert g["fresh_count"] == 0
    assert "2 expired soft-allows" in g["line"]
    assert "breadth×1" in g["line"]
    assert "promote×1" in g["line"]
