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
    assert g["severity"] == "hot"
    assert g["count"] == 1
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["aging_hours"] == 12.0
    assert g["last_gate"] == "regime"
    assert g["line"].startswith("hot · ")
    assert "1 recent soft-allow" in g["line"]
    assert "[regime]" in g["line"]
    assert "no SPY bars" in g["line"]


def test_soft_allow_glance_truncates_reason() -> None:
    long = "x" * 100
    g = build_soft_allow_glance([{"at": "t", "gate": "rs", "reason": long}])
    assert g["ready"] is True
    assert g["last_reason"].endswith("…")
    assert len(g["last_reason"]) <= 72


def test_soft_allow_glance_speaks_aging() -> None:
    """xang1234 / RyanJHamby: aging (>12h) speaks before expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["count"] == 2
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == ""
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "2 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "expired" not in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_consolidates_expired() -> None:
    """tradermonty #437: expired soft-allows speak count + gate tally."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": stale, "gate": "regime", "reason": "unknown — no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "unknown — no BTC bars"},
        ],
        now=now,
        fresh_hours=24.0,
    )
    assert g["count"] == 4
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 2
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == "regime×2"
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "4 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "2 expired" in g["line"]
    assert "regime×2" in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_aging_tally_only() -> None:
    """Aging-only ledger consolidates gates like the expired all-expired path."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["aging_count"] == 3
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == ""
    assert g["aging_tally"] == "breadth×2 · rs×1"
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"
    assert g["line"].startswith("aging · ")
    assert "3 soft-allows" in g["line"]
    assert "3 aging" in g["line"]
    assert "breadth×2" in g["line"]
    assert "rs×1" in g["line"]
    assert "fresh" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_fresh_tally_mixed() -> None:
    """portfolio AI + xang1234: fresh gate tally beside aging/expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY bars"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 2
    assert g["aging_count"] == 1
    assert g["fresh_tally"] == "regime×1 · rs×1"
    assert "2 fresh" in g["line"]
    assert "regime×1" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]


def test_soft_allow_glance_fresh_tally_multi_recent() -> None:
    """All-fresh multi-gate ledger consolidates without aging noise."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 3
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×2 · breadth×1"
    assert "3 recent soft-allows" in g["line"]
    assert "rs×2" in g["line"]
    assert "breadth×1" in g["line"]
    assert "aging" not in g["line"]
    assert "expired" not in g["line"]


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
    assert g["aging_count"] == 0
    assert g["severity"] == "cool"
    assert g["tone"] == "flat"
    assert g["line"].startswith("cool · ")
    assert "2 expired soft-allows" in g["line"]
    assert "breadth×1" in g["line"]
    assert "promote×1" in g["line"]


def test_soft_allow_glance_cool_off_severity_triad() -> None:
    """portfolio AI + xang1234: hot / aging / cool — expired is not warn."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hot = build_soft_allow_glance(
        [{"at": fresh, "gate": "rs", "reason": "insufficient"}],
        now=now,
    )
    cooling = build_soft_allow_glance(
        [{"at": aging, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    cool = build_soft_allow_glance(
        [{"at": stale, "gate": "regime", "reason": "no SPY bars"}],
        now=now,
    )
    assert (hot["severity"], hot["tone"]) == ("hot", "warn")
    assert (cooling["severity"], cooling["tone"]) == ("aging", "flat")
    assert (cool["severity"], cool["tone"]) == ("cool", "flat")
