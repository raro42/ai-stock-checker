"""Scan archive age honesty (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytz

from openbb_backend.desk import (
    build_scan_freshness,
    cash_print_band_size,
    gap_cursor_pin_size,
    scan_archive_pin_size,
    soft_allow_pin_size,
    cash_print_freshness,
    memory_own_pin_size,
    memory_peer_cash_clock_clash,
    memory_peer_gap_clock_clash,
    memory_peer_short_clock_clash,
    memory_peer_soft_clock_clash,
    memory_vs_cash_clock_clash,
    soft_allow_gap_last_clock_tone,
    soft_allow_last_clock_tone,
    soft_allow_short_history_last_clock_tone,
    soft_allow_vs_cash_clock_clash,
    _coerce_scan_interval_min_to_sec,
    _coerce_scan_interval_sec,
    _scan_vs_cash_clash_delta,
    _scan_vs_cash_delta_vs_sleeve,
    _scan_vs_cash_print_clash,
)


def test_coerce_scan_interval_refuses_bool() -> None:
    """tradermonty #700/#655: True→1s / True→1m must not invent freshness."""
    assert _coerce_scan_interval_sec(True) == 900
    assert _coerce_scan_interval_sec(False) == 900
    assert _coerce_scan_interval_sec(None) == 900
    assert _coerce_scan_interval_sec(120) == 120
    assert _coerce_scan_interval_sec(30) == 60  # floor
    assert _coerce_scan_interval_min_to_sec(True) == 900
    assert _coerce_scan_interval_min_to_sec(False) == 900
    assert _coerce_scan_interval_min_to_sec(None) == 900
    assert _coerce_scan_interval_min_to_sec(20) == 1200


def test_scan_freshness_refuses_bool_interval() -> None:
    """Bool 1s interval would mark a 30s-old scan stale — keep default 900s."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stamp = "2026-09-23T11:59:30Z"  # 30s old
    g = build_scan_freshness(
        stamp, now=now, scan_interval_sec=True  # type: ignore[arg-type]
    )
    assert g["tone"] == "fresh"
    g_ok = build_scan_freshness(stamp, now=now, scan_interval_sec=900)
    assert g_ok["tone"] == "fresh"


def test_scan_archive_pin_size() -> None:
    """Sole published scan archive → scan-only (#647/#531 soft≠scan wire)."""
    assert scan_archive_pin_size(scan_freshness="fresh") == " · scan-only"
    assert scan_archive_pin_size(scan_freshness="aging") == " · scan-only"
    assert scan_archive_pin_size(scan_freshness="stale") == " · scan-only"
    assert scan_archive_pin_size(scan_freshness="expired") == " · scan-only"
    assert scan_archive_pin_size(scan_freshness="unknown") == " · scan-only"
    assert scan_archive_pin_size(scan_freshness="") == ""
    assert scan_archive_pin_size() == ""


def test_soft_allow_pin_size() -> None:
    """Sole soft last pin → soft-only (#647/#531 LAYA/debate≠soft wire)."""
    assert soft_allow_pin_size(soft_freshness="fresh") == " · soft-only"
    assert soft_allow_pin_size(soft_freshness="aging") == " · soft-only"
    assert soft_allow_pin_size(soft_freshness="stale") == " · soft-only"
    assert soft_allow_pin_size(soft_freshness="expired") == " · soft-only"
    assert soft_allow_pin_size(soft_freshness="unknown") == " · soft-only"
    assert soft_allow_pin_size(soft_freshness="") == ""
    assert soft_allow_pin_size() == ""


def test_memory_own_pin_size() -> None:
    """Sole own advisory pin → laya-only|debate-only (#647/#531 ≠soft/scan/gap/cash)."""
    assert memory_own_pin_size(side="laya", freshness="fresh") == " · laya-only"
    assert memory_own_pin_size(side="debate", freshness="aging") == " · debate-only"
    assert memory_own_pin_size(side="laya", freshness="expired") == " · laya-only"
    assert memory_own_pin_size(side="debate", freshness="unknown") == " · debate-only"
    assert memory_own_pin_size(side="laya", freshness="") == ""
    assert memory_own_pin_size(side="soft", freshness="fresh") == ""
    assert memory_own_pin_size(side="", freshness="fresh") == ""


def test_gap_cursor_pin_size() -> None:
    """Sole gap cursor pin → gap-only (#647/#531 LAYA/debate≠gap wire)."""
    assert gap_cursor_pin_size(gap_freshness="fresh") == " · gap-only"
    assert gap_cursor_pin_size(gap_freshness="aging") == " · gap-only"
    assert gap_cursor_pin_size(gap_freshness="stale") == " · gap-only"
    assert gap_cursor_pin_size(gap_freshness="expired") == " · gap-only"
    assert gap_cursor_pin_size(gap_freshness="unknown") == " · gap-only"
    assert gap_cursor_pin_size(gap_freshness="") == ""
    assert gap_cursor_pin_size() == ""


def test_cash_print_band_size() -> None:
    """Sole pin → venue-only; dual half → named venue · 50% (#647/#531)."""
    both = {
        "cash_print_us_last_published": True,
        "cash_print_us_freshness": "aging",
        "cash_print_xetra_last_published": True,
        "cash_print_xetra_freshness": "aging",
    }
    assert cash_print_band_size(both, clock="aging") == " · ×2 · 100%"
    split = {
        "cash_print_us_last_published": True,
        "cash_print_us_freshness": "stale",
        "cash_print_xetra_last_published": True,
        "cash_print_xetra_freshness": "aging",
    }
    assert cash_print_band_size(split, clock="stale") == " · US · 50%"
    assert cash_print_band_size(split, clock="aging") == " · Xetra · 50%"
    assert cash_print_band_size(split, clock="fresh") == ""
    us_only = {
        "cash_print_us_last_published": True,
        "cash_print_us_freshness": "aging",
        "cash_print_xetra_last_published": False,
        "cash_print_xetra_freshness": "",
    }
    assert cash_print_band_size(us_only, clock="aging") == " · US-only"
    xetra_only = {
        "cash_print_us_last_published": False,
        "cash_print_us_freshness": "",
        "cash_print_xetra_last_published": True,
        "cash_print_xetra_freshness": "stale",
    }
    assert cash_print_band_size(xetra_only, clock="stale") == " · Xetra-only"
    assert cash_print_band_size(us_only, clock="stale") == ""
    assert cash_print_band_size({}, clock="aging") == ""
    assert cash_print_band_size(None, clock="aging") == ""


def test_soft_allow_vs_cash_clock_clash_helper() -> None:
    """Soft last ≠ pinned cash closes soft↔cash↔scan (display only)."""
    assert soft_allow_vs_cash_clock_clash("fresh", "aging") == (
        "clash · soft fresh · cash aging",
        True,
    )
    assert soft_allow_vs_cash_clock_clash("expired", "fresh") == (
        "clash · soft stale · cash fresh",
        True,
    )
    assert soft_allow_vs_cash_clock_clash("stale", "stale") == ("", False)
    assert soft_allow_vs_cash_clock_clash("fresh", "") == ("", False)
    assert soft_allow_vs_cash_clock_clash("", "stale") == ("", False)
    assert soft_allow_vs_cash_clock_clash("unknown", "aging") == (
        "clash · soft fresh · cash aging",
        True,
    )
    assert memory_vs_cash_clock_clash("fresh", "aging", side="laya") == (
        "clash · laya fresh · cash aging",
        True,
    )
    assert memory_vs_cash_clock_clash("fresh", "aging", side="debate") == (
        "clash · debate fresh · cash aging",
        True,
    )


def test_soft_allow_last_clock_tone_helper(tmp_path) -> None:
    """Newest soft-allow maps expired→stale for memory speak-both-sides."""
    import json
    from datetime import timedelta

    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    assert soft_allow_last_clock_tone(tmp_path, now=now) == ""
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert soft_allow_last_clock_tone(tmp_path, now=now) == "stale"


def test_memory_peer_cash_clock_clash_helper() -> None:
    """Own matching cash + peer ≠ cash speaks peer (display only)."""
    assert memory_peer_cash_clock_clash(
        "fresh", "aging", "fresh", peer_side="debate"
    ) == ("peer cash · debate aging · cash fresh", True)
    assert memory_peer_cash_clock_clash(
        "fresh", "stale", "fresh", peer_side="laya"
    ) == ("peer cash · laya stale · cash fresh", True)
    # Own already clashes — peer bit stays on the other glance.
    assert memory_peer_cash_clock_clash(
        "fresh", "aging", "aging", peer_side="debate"
    ) == ("", False)
    # Both match cash — silent.
    assert memory_peer_cash_clock_clash(
        "fresh", "fresh", "fresh", peer_side="debate"
    ) == ("", False)
    assert memory_peer_cash_clock_clash(
        "fresh", "", "aging", peer_side="debate"
    ) == ("", False)


def test_memory_peer_soft_clock_clash_helper() -> None:
    """Own matching soft + peer ≠ soft speaks peer (display only)."""
    assert memory_peer_soft_clock_clash(
        "fresh", "aging", "fresh", peer_side="debate"
    ) == ("peer soft · debate aging · soft fresh", True)
    assert memory_peer_soft_clock_clash(
        "fresh", "stale", "fresh", peer_side="laya"
    ) == ("peer soft · laya stale · soft fresh", True)
    # expired≡stale — own stale matching soft + peer fresh speaks.
    assert memory_peer_soft_clock_clash(
        "stale", "fresh", "expired", peer_side="debate"
    ) == ("peer soft · debate fresh · soft stale", True)
    # Own already clashes — peer bit stays on the other glance.
    assert memory_peer_soft_clock_clash(
        "fresh", "aging", "aging", peer_side="debate"
    ) == ("", False)
    # Both match soft — silent.
    assert memory_peer_soft_clock_clash(
        "fresh", "fresh", "fresh", peer_side="debate"
    ) == ("", False)
    assert memory_peer_soft_clock_clash(
        "fresh", "", "fresh", peer_side="debate"
    ) == ("", False)


def test_soft_allow_gap_last_clock_tone_helper(tmp_path) -> None:
    """Newest gap maps expired→stale; soft last alone ≠ gap cursor."""
    import json
    from datetime import timedelta

    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    assert soft_allow_gap_last_clock_tone(tmp_path, now=now) == ""
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Oldest-first file: stale gap then fresh non-gap soft last.
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    },
                    {
                        "at": fresh_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert soft_allow_last_clock_tone(tmp_path, now=now) == "fresh"
    assert soft_allow_gap_last_clock_tone(tmp_path, now=now) == "stale"


def test_memory_peer_gap_clock_clash_helper() -> None:
    """Own matching gap + peer ≠ gap speaks peer (display only)."""
    assert memory_peer_gap_clock_clash(
        "fresh", "aging", "fresh", peer_side="debate"
    ) == ("peer gap · debate aging · gap fresh", True)
    assert memory_peer_gap_clock_clash(
        "fresh", "stale", "fresh", peer_side="laya"
    ) == ("peer gap · laya stale · gap fresh", True)
    assert memory_peer_gap_clock_clash(
        "stale", "fresh", "expired", peer_side="debate"
    ) == ("peer gap · debate fresh · gap stale", True)
    assert memory_peer_gap_clock_clash(
        "fresh", "aging", "aging", peer_side="debate"
    ) == ("", False)
    assert memory_peer_gap_clock_clash(
        "fresh", "fresh", "fresh", peer_side="debate"
    ) == ("", False)
    assert memory_peer_gap_clock_clash(
        "fresh", "", "fresh", peer_side="debate"
    ) == ("", False)


def test_memory_peer_short_clock_clash_helper() -> None:
    """Own matching short + peer ≠ short speaks peer (display only)."""
    assert memory_peer_short_clock_clash(
        "fresh", "aging", "fresh", peer_side="debate"
    ) == ("peer short · debate aging · short fresh", True)
    assert memory_peer_short_clock_clash(
        "fresh", "stale", "fresh", peer_side="laya"
    ) == ("peer short · laya stale · short fresh", True)
    assert memory_peer_short_clock_clash(
        "stale", "fresh", "expired", peer_side="debate"
    ) == ("peer short · debate fresh · short stale", True)
    assert memory_peer_short_clock_clash(
        "fresh", "aging", "aging", peer_side="debate"
    ) == ("", False)
    assert memory_peer_short_clock_clash(
        "fresh", "fresh", "fresh", peer_side="debate"
    ) == ("", False)
    assert memory_peer_short_clock_clash(
        "fresh", "", "fresh", peer_side="debate"
    ) == ("", False)


def test_soft_allow_short_history_last_clock_tone(
    tmp_path, monkeypatch
) -> None:
    """Newest short-history cursor maps expired→stale (display only)."""
    import json
    from datetime import datetime, timedelta, timezone

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "IPO RS unknown — short history — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert soft_allow_short_history_last_clock_tone(tmp_path, now=now) == "stale"
    assert soft_allow_short_history_last_clock_tone(tmp_path / "missing") == ""


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
    assert g["scan_vs_cash_clash_delta_vs_sleeve"] == ""
    assert g["scan_vs_cash_clash_delta_vs_sleeve_warn"] is False
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
        "scan vs cash clash · scan fresh · cash aging"
        " · scan-only · ×2 · 100% · Δ thin"
    )
    assert g["scan_vs_cash_print"] == "aging"
    assert g["scan_vs_cash_clash_delta"] == "thin"
    assert g["scan_vs_cash_clash_sleeve_delta"] == ""
    assert g["scan_vs_cash_clash_delta_vs_sleeve"] == ""
    assert g["scan_vs_cash_clash_delta_vs_sleeve_warn"] is False
    assert g["scan_vs_cash_clash_runner"] == ""
    assert "scan vs cash clash" in g["line"]
    assert "×2 · 100%" in g["line"]
    assert "Δ thin" in g["line"]


def test_cash_print_freshness_bands() -> None:
    assert cash_print_freshness(0) == "fresh"
    assert cash_print_freshness(11 * 3600) == "fresh"
    assert cash_print_freshness(12 * 3600) == "aging"
    assert cash_print_freshness(35 * 3600) == "aging"
    assert cash_print_freshness(36 * 3600) == "stale"


def test_cash_print_and_age_helpers_refuse_bool() -> None:
    """tradermonty #700/#655: True→1s must not invent fresh / just now / lag <1m."""
    from openbb_backend.desk import (
        _format_age_short,
        _format_pin_lag,
        _pin_lag_severity,
    )

    assert cash_print_freshness(True) == "stale"
    assert cash_print_freshness(False) == "stale"
    assert cash_print_freshness(None) == "stale"
    assert _format_age_short(True) == "n/a"
    assert _format_age_short(False) == "n/a"
    assert _format_age_short(0) == "just now"
    assert _pin_lag_severity(True) == "stale"
    assert _pin_lag_severity(False) == "stale"
    assert _format_pin_lag(True) == "lag n/a"
    assert _format_pin_lag(False, severity="stale") == "lag n/a · stale"
    assert _format_pin_lag(30) == "lag <1m"


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
        "scan vs cash clash · scan fresh · cash stale"
        " · scan-only · ×2 · 100% · Δ wide"
    )
    assert g["scan_vs_cash_print"] == "stale"
    assert g["scan_vs_cash_clash_delta"] == "wide"
    assert g["scan_vs_cash_clash_sleeve_delta"] == ""
    assert g["scan_vs_cash_clash_delta_vs_sleeve"] == ""
    assert g["scan_vs_cash_clash_delta_vs_sleeve_warn"] is False
    assert g["scan_vs_cash_clash_runner"] == ""
    assert "scan vs cash clash" in g["line"]
    assert "×2 · 100%" in g["line"]
    assert "Δ wide" in g["line"]


def test_scan_vs_cash_clash_delta_bands() -> None:
    assert _scan_vs_cash_clash_delta("fresh", "aging") == "thin"
    assert _scan_vs_cash_clash_delta("aging", "stale") == "thin"
    assert _scan_vs_cash_clash_delta("fresh", "stale") == "wide"
    assert _scan_vs_cash_clash_delta("stale", "fresh") == "wide"
    assert _scan_vs_cash_clash_delta("fresh", "fresh") == ""
    assert _scan_vs_cash_clash_delta("fresh", "") == ""


def test_scan_vs_cash_delta_vs_sleeve() -> None:
    """portfolio AI: scan↔cash Δ vs pin sleeve Δ is not two silent labels."""
    assert _scan_vs_cash_delta_vs_sleeve("thin", "thin") == (
        "align · both thin",
        False,
    )
    assert _scan_vs_cash_delta_vs_sleeve("wide", "wide") == (
        "align · both wide",
        True,
    )
    assert _scan_vs_cash_delta_vs_sleeve("wide", "thin") == (
        "clash · Δ wide · sleeve thin",
        True,
    )
    assert _scan_vs_cash_delta_vs_sleeve("thin", "wide") == (
        "clash · Δ thin · sleeve wide",
        True,
    )
    assert _scan_vs_cash_delta_vs_sleeve("thin", "") == ("", False)
    assert _scan_vs_cash_delta_vs_sleeve("", "wide") == ("", False)


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
    assert g["scan_vs_cash_clash_delta_vs_sleeve"] == "align · both thin"
    assert g["scan_vs_cash_clash_delta_vs_sleeve_warn"] is False
    assert g["scan_vs_cash_clash"] == (
        "scan vs cash clash · scan fresh · Xetra cash aging · US fresh"
        " · scan-only · Xetra · 50% · Δ thin · sleeve Δ thin"
        " · Δ vs sleeve Δ align · both thin · runner · US · 50%"
    )
    assert "Xetra · 50%" in g["line"]
    assert "sleeve Δ thin" in g["line"]
    assert "Δ vs sleeve Δ align · both thin" in g["line"]
    assert "runner · US · 50%" in g["line"]


def test_scan_freshness_delta_vs_sleeve_clash() -> None:
    """Fresh scan + stale Xetra + aging US → wide scan Δ vs thin sleeve Δ."""
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
    clash_delta = _scan_vs_cash_clash_delta("fresh", cash)
    sleeve_delta = _scan_vs_cash_clash_delta(cash, runner)
    assert clash_delta == "wide"
    assert sleeve_delta == "thin"
    bit, warn = _scan_vs_cash_delta_vs_sleeve(clash_delta, sleeve_delta)
    assert bit == "clash · Δ wide · sleeve thin"
    assert warn is True
    assert "Xetra cash stale · US aging" in clash
