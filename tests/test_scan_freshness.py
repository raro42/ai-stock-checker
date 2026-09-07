"""Scan archive age honesty (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

from openbb_backend.desk import build_scan_freshness


def test_scan_freshness_empty() -> None:
    assert build_scan_freshness(None)["ready"] is False
    assert build_scan_freshness("")["ready"] is False


def test_scan_freshness_fresh() -> None:
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    g = build_scan_freshness(
        "2026-09-08T01:20:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["tone"] == "fresh"
    assert g["age_label"] == "10m ago"
    assert "fresh" in g["line"]


def test_scan_freshness_aging() -> None:
    now = datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc)
    g = build_scan_freshness(
        "2026-09-08T01:00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["tone"] == "aging"
    assert g["age_label"] == "1h ago"


def test_scan_freshness_stale() -> None:
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    g = build_scan_freshness(
        "2026-09-08T01:00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["tone"] == "stale"
    assert g["age_label"] == "11h ago"


def test_scan_freshness_unparsed() -> None:
    g = build_scan_freshness("not-a-time")
    assert g["ready"] is True
    assert g["tone"] == "unknown"
    assert "age unknown" in g["line"]
