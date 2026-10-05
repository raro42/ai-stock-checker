"""Scan archive age honesty (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytz

from openbb_backend.desk import build_scan_freshness, cash_print_freshness


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
    assert g["age_label"] == "10m ago"
    assert "10m ago" not in g["provenance_bit"]
    assert "h ago" in g["provenance_bit"]
    assert g["cash_print_us_freshness"] == "fresh"
    assert g["cash_print_xetra_freshness"] == "fresh"
    assert "fresh" in g["provenance_bit"]
    assert g["scan_vs_cash_clash"] == ""


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
    assert "h ago" in g["provenance_bit"] or "d ago" in g["provenance_bit"]
    assert g["cash_print_us_freshness"] in ("fresh", "aging", "stale")
    assert g["cash_print_us_freshness"] in g["provenance_bit"]
    if g["cash_print_us_freshness"] != g["tone"]:
        assert "scan vs cash clash" in g["scan_vs_cash_clash"]
        assert g["scan_vs_cash_print"] == g["cash_print_us_freshness"]
    else:
        assert g["scan_vs_cash_clash"] == ""


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
    assert "h ago" in g["provenance_bit"] or "d ago" in g["provenance_bit"]
    assert g["cash_print_xetra_freshness"] in ("fresh", "aging", "stale")
    assert g["cash_print_xetra_freshness"] in g["provenance_bit"]
    if g["cash_print_xetra_freshness"] != g["tone"]:
        assert "scan vs cash clash" in g["scan_vs_cash_clash"]
        assert g["scan_vs_cash_print"] == g["cash_print_xetra_freshness"]
    else:
        assert g["scan_vs_cash_clash"] == ""


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
    assert g["scan_vs_cash_clash"] == ""


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
    assert "US " in g["provenance_bit"]
    assert "Xetra " in g["provenance_bit"]
    assert "ago" in g["provenance_bit"]
    assert g["cash_print_us_freshness"] == "aging"
    assert g["cash_print_xetra_freshness"] == "aging"
    assert "aging" in g["provenance_bit"]
    assert g["scan_vs_cash_clash"] == "scan vs cash clash · scan fresh · cash aging"
    assert g["scan_vs_cash_print"] == "aging"
    assert "scan vs cash clash" in g["line"]


def test_cash_print_freshness_bands() -> None:
    assert cash_print_freshness(0) == "fresh"
    assert cash_print_freshness(11 * 3600) == "fresh"
    assert cash_print_freshness(12 * 3600) == "aging"
    assert cash_print_freshness(35 * 3600) == "aging"
    assert cash_print_freshness(36 * 3600) == "stale"


def test_scan_freshness_weekend_sunday_cash_print_stale() -> None:
    """RyanJHamby: Friday close is a stale print by Sunday, not just 'Nd ago'."""
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 13, 12, 0))
    g = build_scan_freshness(
        "2026-09-13T15:50:00+00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["provenance"] == "last_published"
    assert g["cash_print_us_freshness"] == "stale"
    assert g["cash_print_xetra_freshness"] == "stale"
    assert "stale" in g["provenance_bit"]
    assert "stocks paused" in g["provenance_bit"]
    assert g["scan_vs_cash_clash"] == "scan vs cash clash · scan fresh · cash stale"
    assert g["scan_vs_cash_print"] == "stale"
    assert "scan vs cash clash" in g["line"]
