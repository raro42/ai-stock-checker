"""Scan archive age honesty (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytz

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
    assert g["provenance"] == ""
    assert g["provenance_bit"] == ""


def test_scan_freshness_last_published_when_cash_closed() -> None:
    """xang1234: fresh scan clock ≠ live US/Xetra quotes after hours."""
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    g = build_scan_freshness(
        "2026-09-08T01:20:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["tone"] == "fresh"
    assert g["provenance"] == "last_published"
    assert "last published" in g["line"]
    assert "US closed" in g["provenance_bit"]
    assert "Xetra closed" in g["provenance_bit"]
    assert "crypto live" in g["provenance_bit"]


def test_scan_freshness_mixed_when_us_closed_xetra_open() -> None:
    now = pytz.timezone("Europe/Berlin").localize(datetime(2026, 9, 9, 10, 0))
    g = build_scan_freshness(
        "2026-09-09T07:55:00+00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["tone"] == "fresh"
    assert g["provenance"] == "mixed"
    assert "compile mixed" in g["provenance_bit"]
    assert "US last-published" in g["provenance_bit"]
    assert "Xetra live" in g["provenance_bit"]
    assert "crypto live" in g["provenance_bit"]
    assert "Xetra last-published" not in g["provenance_bit"]


def test_scan_freshness_mixed_when_us_open_xetra_closed() -> None:
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 9, 15, 0))
    g = build_scan_freshness(
        "2026-09-09T18:55:00+00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["tone"] == "fresh"
    assert g["provenance"] == "mixed"
    assert "US live" in g["provenance_bit"]
    assert "Xetra last-published" in g["provenance_bit"]
    assert "crypto live" in g["provenance_bit"]


def test_scan_freshness_live_when_both_cash_open() -> None:
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 9, 10, 0))
    g = build_scan_freshness(
        "2026-09-09T13:55:00+00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["tone"] == "fresh"
    assert g["provenance"] == "live"
    assert g["provenance_bit"] == ""
    assert "last published" not in g["line"]
    assert "crypto live" not in g["line"]


def test_scan_freshness_weekend_stocks_paused() -> None:
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 12, 12, 0))
    g = build_scan_freshness(
        "2026-09-12T15:50:00+00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["provenance"] == "last_published"
    assert "stocks paused" in g["provenance_bit"]
    assert "crypto live" in g["provenance_bit"]
