"""Scan archive age honesty (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytz

from openbb_backend.desk import (
    build_scan_freshness,
    cash_print_freshness,
    _scan_vs_cash_clash_delta,
    _scan_vs_cash_print_clash,
)


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
    assert g["scan_vs_cash_clash_delta"] == ""
    assert g["scan_vs_cash_clash_sleeve_delta"] == ""
    assert g["scan_vs_cash_clash_runner"] == ""


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
        assert f"US cash {g['cash_print_us_freshness']}" in g["scan_vs_cash_clash"]
        assert g["scan_vs_cash_print"] == g["cash_print_us_freshness"]
        assert g["scan_vs_cash_clash_delta"] in ("wide", "thin")
        assert f"Δ {g['scan_vs_cash_clash_delta']}" in g["scan_vs_cash_clash"]
        assert g["scan_vs_cash_clash_sleeve_delta"] == ""
        assert g["scan_vs_cash_clash_runner"] == ""
    else:
        assert g["scan_vs_cash_clash"] == ""
        assert g["scan_vs_cash_clash_delta"] == ""
        assert g["scan_vs_cash_clash_sleeve_delta"] == ""
        assert g["scan_vs_cash_clash_runner"] == ""


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
        assert (
            f"Xetra cash {g['cash_print_xetra_freshness']}" in g["scan_vs_cash_clash"]
        )
        assert g["scan_vs_cash_print"] == g["cash_print_xetra_freshness"]
        assert g["scan_vs_cash_clash_delta"] in ("wide", "thin")
        assert f"Δ {g['scan_vs_cash_clash_delta']}" in g["scan_vs_cash_clash"]
        assert g["scan_vs_cash_clash_sleeve_delta"] == ""
        assert g["scan_vs_cash_clash_runner"] == ""
    else:
        assert g["scan_vs_cash_clash"] == ""
        assert g["scan_vs_cash_clash_delta"] == ""
        assert g["scan_vs_cash_clash_sleeve_delta"] == ""
        assert g["scan_vs_cash_clash_runner"] == ""


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
    assert g["scan_vs_cash_clash_delta"] == ""
    assert g["scan_vs_cash_clash_sleeve_delta"] == ""
    assert g["scan_vs_cash_clash_runner"] == ""


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
    assert g["scan_vs_cash_clash"] == (
        "scan vs cash clash · scan fresh · cash aging · Δ thin"
    )
    assert g["scan_vs_cash_print"] == "aging"
    assert g["scan_vs_cash_clash_delta"] == "thin"
    assert g["scan_vs_cash_clash_sleeve_delta"] == ""
    assert g["scan_vs_cash_clash_runner"] == ""
    assert "scan vs cash clash" in g["line"]
    assert "Δ thin" in g["line"]


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
    assert g["scan_vs_cash_clash"] == (
        "scan vs cash clash · scan fresh · cash stale · Δ wide"
    )
    assert g["scan_vs_cash_print"] == "stale"
    assert g["scan_vs_cash_clash_delta"] == "wide"
    assert g["scan_vs_cash_clash_sleeve_delta"] == ""
    assert g["scan_vs_cash_clash_runner"] == ""
    assert "scan vs cash clash" in g["line"]
    assert "Δ wide" in g["line"]


def test_scan_vs_cash_clash_delta_bands() -> None:
    assert _scan_vs_cash_clash_delta("fresh", "aging") == "thin"
    assert _scan_vs_cash_clash_delta("aging", "stale") == "thin"
    assert _scan_vs_cash_clash_delta("fresh", "stale") == "wide"
    assert _scan_vs_cash_clash_delta("stale", "fresh") == "wide"
    assert _scan_vs_cash_clash_delta("fresh", "fresh") == ""
    assert _scan_vs_cash_clash_delta("fresh", "") == ""


def test_scan_vs_cash_clash_names_market_pointer_when_sleeves_differ() -> None:
    """xang1234 #531: worst sleeve owns the clash label, not a nameless cash."""
    clash, cash, runner = _scan_vs_cash_print_clash(
        "fresh",
        {
            "cash_print_us_last_published": True,
            "cash_print_us_freshness": "stale",
            "cash_print_xetra_last_published": True,
            "cash_print_xetra_freshness": "aging",
        },
    )
    assert cash == "stale"
    assert runner == "aging"
    assert clash == (
        "scan vs cash clash · scan fresh · US cash stale · Xetra aging"
    )

    clash_both, cash_both, runner_both = _scan_vs_cash_print_clash(
        "fresh",
        {
            "cash_print_us_last_published": True,
            "cash_print_us_freshness": "stale",
            "cash_print_xetra_last_published": True,
            "cash_print_xetra_freshness": "stale",
        },
    )
    assert cash_both == "stale"
    assert runner_both == ""
    assert clash_both == "scan vs cash clash · scan fresh · cash stale"

    clash_xetra, cash_xetra, runner_xetra = _scan_vs_cash_print_clash(
        "fresh",
        {
            "cash_print_us_last_published": False,
            "cash_print_us_freshness": "",
            "cash_print_xetra_last_published": True,
            "cash_print_xetra_freshness": "aging",
        },
    )
    assert cash_xetra == "aging"
    assert runner_xetra == ""
    assert clash_xetra == "scan vs cash clash · scan fresh · Xetra cash aging"


def test_scan_vs_cash_clash_speaks_runner_sleeve() -> None:
    """portfolio AI: market-pointer worst + calmer runner, not a lone label."""
    clash, cash, runner = _scan_vs_cash_print_clash(
        "fresh",
        {
            "cash_print_us_last_published": True,
            "cash_print_us_freshness": "aging",
            "cash_print_xetra_last_published": True,
            "cash_print_xetra_freshness": "stale",
        },
    )
    assert cash == "stale"
    assert runner == "aging"
    assert clash == (
        "scan vs cash clash · scan fresh · Xetra cash stale · US aging"
    )


def test_scan_vs_cash_clash_sleeve_delta_after_runner() -> None:
    """xang1234 share-Δ: worst↔runner gap is not the scan↔cash Δ."""
    clash, cash, runner = _scan_vs_cash_print_clash(
        "fresh",
        {
            "cash_print_us_last_published": True,
            "cash_print_us_freshness": "fresh",
            "cash_print_xetra_last_published": True,
            "cash_print_xetra_freshness": "stale",
        },
    )
    assert cash == "stale"
    assert runner == "fresh"
    assert _scan_vs_cash_clash_delta("fresh", cash) == "wide"
    assert _scan_vs_cash_clash_delta(cash, runner) == "wide"
    assert clash == (
        "scan vs cash clash · scan fresh · Xetra cash stale · US fresh"
    )


def test_scan_freshness_weekend_morning_sleeve_delta() -> None:
    """Saturday morning: Xetra aging vs US still-fresh Friday close."""
    now = datetime(2026, 9, 12, 5, 0, tzinfo=timezone.utc)
    g = build_scan_freshness(
        "2026-09-12T04:50:00+00:00",
        now=now,
        scan_interval_sec=900,
    )
    assert g["provenance"] == "last_published"
    assert g["tone"] == "fresh"
    assert g["cash_print_us_freshness"] == "fresh"
    assert g["cash_print_xetra_freshness"] == "aging"
    assert g["scan_vs_cash_print"] == "aging"
    assert g["scan_vs_cash_clash_runner"] == "fresh"
    assert g["scan_vs_cash_clash_delta"] == "thin"
    assert g["scan_vs_cash_clash_sleeve_delta"] == "thin"
    assert g["scan_vs_cash_clash"] == (
        "scan vs cash clash · scan fresh · Xetra cash aging · US fresh"
        " · Δ thin · sleeve Δ thin"
    )
    assert "sleeve Δ thin" in g["line"]
