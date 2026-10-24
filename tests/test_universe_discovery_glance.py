"""Universe / Yahoo movers discovery glance (display only; cache age)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_universe_discovery_glance, load_desk_snapshot
from stock_checker.yahoo_universe_discovery import (
    DEFAULT_MOVER_COUNT,
    DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS,
)


def test_universe_discovery_glance_never_run(tmp_path) -> None:
    g = build_universe_discovery_glance(tmp_path)
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert g["seed_freshness"] == "never"
    assert g["discovery_only"] is True
    assert g["auto_buy"] is False
    assert g["mover_count"] == int(DEFAULT_MOVER_COUNT)
    assert g["max_age_hours"] == int(DEFAULT_YAHOO_DISCOVERY_MAX_AGE_HOURS)
    assert g["age_label"] == "never"
    assert "cache never" in g["line"]
    assert "discovery-only" in g["line"]
    assert f"≤{DEFAULT_MOVER_COUNT}" in g["line"]


def test_universe_discovery_glance_fresh_cache(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {},
                "meta": {"last_yahoo_discovery": last, "last_yahoo_added": 2},
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["tone"] == "fresh"
    assert g["last_yahoo_added"] == 2
    assert g["last_yahoo_dropped"] is None
    assert "dropped" not in g["line"]
    assert g["age_sec"] == 6 * 3600
    assert g["yahoo_retry_due"] is False
    assert "cache 6h ago" in g["line"]
    assert "fresh" in g["line"]
    assert "retry due" not in g["line"]


def test_universe_discovery_glance_aging_and_stale(tmp_path) -> None:
    now = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
    aging_last = (now - timedelta(hours=30)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps({"meta": {"last_yahoo_discovery": aging_last}}),
        encoding="utf-8",
    )
    aging = build_universe_discovery_glance(tmp_path, now=now)
    assert aging["tone"] == "aging"
    assert "aging" in aging["line"]

    stale_last = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps({"meta": {"last_yahoo_discovery": stale_last}}),
        encoding="utf-8",
    )
    stale = build_universe_discovery_glance(tmp_path, now=now)
    assert stale["tone"] == "stale"
    assert "stale" in stale["line"]


def test_universe_discovery_glance_yahoo_fail_reuses_seed(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_added": 2,
                    "last_yahoo_discovery_status": "failed",
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["tone"] == "warn"
    assert g["yahoo_failed"] is True
    assert g["yahoo_retry_due"] is True
    assert g["yahoo_fail_streak"] == 0
    assert g["age_label"]
    assert g["seed_freshness"] == "fresh"
    assert "Yahoo fail" in g["line"]
    assert "seed 6h ago · fresh" in g["line"]
    assert "retry due" in g["line"]
    assert "discovery-only" not in g["line"]
    assert g["last_yahoo_added"] == 2
    assert g["screens_bit"] == ""
    # First fail / missing streak: no N× chip (xang1234 #639).
    assert "×" not in g["line"]


def test_universe_discovery_glance_yahoo_fail_plan_retry_held(tmp_path) -> None:
    """FinRobot #119: plan → retry held · plan; due stays False (no auto-retry)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    # Fail stamp older than default 1h backoff — plan still not due.
    fail = (now - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "last_yahoo_discovery_error": "plan",
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_fail_error"] == "plan"
    assert g["yahoo_retry_due"] is False
    assert g["yahoo_retry_held_plan"] is True
    assert "retry held · plan" in g["line"]
    assert "retry held · plan" in g["line_core"]
    assert "retry due" not in g["line"]
    assert "retry due" not in g["line_core"]
    assert "retry in" not in g["line_core"]
    # Cooling plan also speaks held (not retry in …).
    cool_fail = (now - timedelta(minutes=15)).replace(tzinfo=None).isoformat()
    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["last_yahoo_discovery_fail"] = cool_fail
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    cool = build_universe_discovery_glance(tmp_path, now=now)
    assert cool["yahoo_retry_held_plan"] is True
    assert "retry held · plan" in cool["line_core"]
    assert "retry in" not in cool["line_core"]
    # Non-plan fail still speaks retry due after backoff.
    meta["meta"]["last_yahoo_discovery_error"] = "http"
    meta["meta"]["last_yahoo_discovery_fail"] = fail
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    http = build_universe_discovery_glance(tmp_path, now=now)
    assert http["yahoo_fail_error"] == "http"
    assert http["yahoo_retry_due"] is True
    assert http["yahoo_retry_held_plan"] is False
    assert "retry due" in http["line_core"]
    assert "retry held · plan" not in http["line_core"]


def test_universe_discovery_glance_yahoo_fail_error_class(tmp_path) -> None:
    """xang1234 #639: last-error class on core line (why ≠ N× alone)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "last_yahoo_discovery_error": "empty",
                    "yahoo_discovery_fail_streak": 2,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_fail_error"] == "empty"
    assert "Yahoo fail · empty · 0/3 · 2×" in g["line_core"]
    assert g["line_core"].index("empty") < g["line_core"].index("0/3")
    assert g["line_core"].index("0/3") < g["line_core"].index("2×")
    # N× owns streak/seed + streak/fail — error/* stays off the line.
    assert g["yahoo_fail_error_vs_seed"] == ""
    assert g["yahoo_fail_error_vs_fail"] == ""
    assert g["yahoo_fail_error_seed_vs_fail"] == ""
    assert g["yahoo_fail_error_vs_budget"] == ""
    assert g["yahoo_fail_error_seed_fail_vs_budget"] == ""
    assert "error/seed" not in g["line_core"]
    assert "error/fail" not in g["line_core"]
    assert "error seed/fail" not in g["line_core"]
    assert "error/budget" not in g["line_core"]
    # Junk class stays silent (allowlist).
    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["last_yahoo_discovery_error"] = "DROP TABLE;"
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    junk = build_universe_discovery_glance(tmp_path, now=now)
    assert junk["yahoo_fail_error"] == ""
    assert "DROP" not in junk["line_core"]
    meta["meta"]["last_yahoo_discovery_error"] = "inflight"
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    held = build_universe_discovery_glance(tmp_path, now=now)
    assert held["yahoo_fail_error"] == "inflight"
    assert held["yahoo_fail_error_also"] == ""
    assert "Yahoo fail · inflight · 0/3 · 2×" in held["line_core"]


def test_universe_discovery_glance_yahoo_fail_error_also_mix(tmp_path) -> None:
    """timeout↔inflight both failed → glance speaks the hidden spend side."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                    "last_yahoo_discovery_error": "inflight",
                    "last_yahoo_timeout_fails": 1,
                    "last_yahoo_inflight_fails": 2,
                    "yahoo_discovery_fail_streak": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_fail_error"] == "inflight"
    assert g["yahoo_fail_error_also"] == "+timeout"
    assert g["yahoo_fail_error_also_counts"] == "1 timeout · 2 held"
    assert g["yahoo_fail_error_also_share"] == "33%"
    assert g["yahoo_fail_error_also_share_pct"] == 33
    assert g["yahoo_fail_error_also_share_severity"] == "ok"
    assert g["yahoo_fail_error_also_vs"] == "vs inflight · 67%"
    assert g["yahoo_fail_error_also_vs_pct"] == 67
    assert g["yahoo_fail_error_also_vs_severity"] == "ok"
    assert g["yahoo_fail_error_also_vs_lean"] == ""
    assert g["yahoo_fail_error_also_vs_lean_warn"] is False
    assert g["yahoo_fail_error_also_vs_delta"] == ""
    assert g["yahoo_fail_error_also_vs_delta_pp"] is None
    assert g["yahoo_fail_timeout_fails"] == 1
    assert g["yahoo_fail_inflight_fails"] == 2
    assert "Yahoo fail · inflight · 0/3 · 2×" in g["line_core"]
    assert "+timeout" not in g["line_core"]
    assert g["mix_lean"] == (
        "+timeout · 1 timeout · 2 held · 33% · vs inflight · 67%"
    )
    assert g["mix_lean_warn"] is False
    assert g["mix_lean_meta"] == (
        "quiet · 4 folds · +timeout · counts · share · vs"
    )
    assert (
        "+timeout · 1 timeout · 2 held · 33% · vs inflight · 67%"
    ) in g["line"]

    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["last_yahoo_discovery_error"] = "timeout"
    meta["meta"]["last_yahoo_timeout_fails"] = 2
    meta["meta"]["last_yahoo_inflight_fails"] = 1
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    timed = build_universe_discovery_glance(tmp_path, now=now)
    assert timed["yahoo_fail_error"] == "timeout"
    assert timed["yahoo_fail_error_also"] == "+held"
    assert timed["yahoo_fail_error_also_share"] == "33%"
    assert timed["yahoo_fail_error_also_vs"] == "vs timeout · 67%"
    assert "Yahoo fail · timeout · 0/3 · 2×" in timed["line_core"]
    assert "+held" not in timed["line_core"]
    assert timed["yahoo_fail_error_also_counts"] == "2 timeout · 1 held"
    assert timed["mix_lean"] == (
        "+held · 2 timeout · 1 held · 33% · vs timeout · 67%"
    )
    assert timed["yahoo_fail_error_also_vs_lean"] == ""

    meta["meta"]["last_yahoo_timeout_fails"] = 1
    meta["meta"]["last_yahoo_inflight_fails"] = 1
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    half = build_universe_discovery_glance(tmp_path, now=now)
    assert half["yahoo_fail_error_also_share_severity"] == "hot"
    assert half["yahoo_fail_error_also_vs_severity"] == "ok"
    assert half["yahoo_fail_error_also_vs_lean"] == (
        "clash · hidden hot · winner ok"
    )
    assert half["yahoo_fail_error_also_vs_lean_warn"] is True
    assert half["yahoo_fail_error_also_vs_delta"] == "Δ thin · 0pp"
    assert half["yahoo_fail_error_also_vs_delta_pp"] == 0
    assert half["yahoo_fail_error_also_vs_delta_severity"] == "thin"
    assert half["yahoo_fail_error_also_vs_delta_lead"] == ""
    assert half["yahoo_fail_error_also_vs_delta_lead_size"] == ""
    assert half["yahoo_fail_error_also_vs_delta_lead_size_x"] is None
    assert half["yahoo_fail_error_also_vs_delta_lead_size_sides"] == ""
    assert half["yahoo_fail_error_also_vs_delta_lead_size_louder_pct"] is None
    assert "33%" not in half["line_core"]
    assert "+held" not in half["line_core"]
    assert half["yahoo_fail_error_also_counts"] == "1 timeout · 1 held"
    assert half["mix_lean_meta"] == "clash · +held · counts · lean · Δ"
    assert half["mix_lean"] == (
        "+held · 1 timeout · 1 held · clash · hidden hot · winner ok"
        " · Δ thin · 0pp"
    )
    assert half["mix_lean_warn"] is True
    assert (
        "Yahoo fail · timeout · +held · 1 timeout · 1 held"
        " · clash · hidden hot · winner ok · Δ thin · 0pp · 0/3 · 2×"
    ) in half["line"]

    meta["meta"]["last_yahoo_discovery_error"] = "inflight"
    meta["meta"]["last_yahoo_timeout_fails"] = 1
    meta["meta"]["last_yahoo_inflight_fails"] = 3
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    owned = build_universe_discovery_glance(tmp_path, now=now)
    assert owned["yahoo_fail_error_also_vs_lean"] == "align · quiet|strong"
    assert owned["yahoo_fail_error_also_vs_lean_warn"] is False
    assert owned["yahoo_fail_error_also_vs_delta"] == "Δ wide · -50pp"
    assert owned["yahoo_fail_error_also_vs_delta_pp"] == -50
    assert owned["yahoo_fail_error_also_vs_delta_severity"] == "wide"
    assert owned["yahoo_fail_error_also_vs_delta_lead"] == "Δ lead · held"
    assert owned["yahoo_fail_error_also_vs_delta_lead_size"] == "Δ lead size · 3×"
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_x"] == 3.0
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides"] == (
        "Δ lead size sides · held 3 · timeout 1"
    )
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_louder_pct"] is None
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_quieter_pct"] is None
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_louder_n"] == 3
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_quieter_n"] == 1
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_delta"] == (
        "Δ lead size sides Δ wide · 2 screens"
    )
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_delta_n"] == 2
    assert (
        owned["yahoo_fail_error_also_vs_delta_lead_size_sides_delta_severity"]
        == "wide"
    )
    assert "+timeout" not in owned["line_core"]
    assert owned["yahoo_fail_error_also_counts"] == "1 timeout · 3 held"
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share"] == (
        "Δ lead size sides share · held 75% · timeout 25%"
    )
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_louder_pct"] == 75
    assert (
        owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_quieter_pct"]
        == 25
    )
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta"] == (
        "Δ lead size sides share Δ wide · +50pp"
    )
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta_pp"] == 50
    assert (
        owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta_severity"]
        == "wide"
    )
    assert owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap"] == (
        "Δ lead size sides share vs gap align · wide"
    )
    assert (
        owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap_verb"]
        == "align"
    )
    assert (
        owned["yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap_warn"]
        is True
    )
    assert owned["mix_lean"] == (
        "+timeout · 1 timeout · 3 held · align · quiet|strong · Δ wide · -50pp"
        " · Δ lead · held · Δ lead size · 3×"
        " · Δ lead size sides · held 3 · timeout 1"
        " · Δ lead size sides Δ wide · 2 screens"
        " · Δ lead size sides share · held 75% · timeout 25%"
        " · Δ lead size sides share Δ wide · +50pp"
        " · Δ lead size sides share vs gap align · wide"
    )
    assert owned["mix_lean_warn"] is True
    assert owned["mix_lean_meta"] == (
        "align · wide · +timeout · counts · lean · Δ · +7"
    )
    assert (
        "Yahoo fail · inflight · +timeout · 1 timeout · 3 held"
        " · align · quiet|strong · Δ wide · -50pp · Δ lead · held"
    ) in owned["line"]
    assert owned["line"].endswith("…")

    meta["meta"]["last_yahoo_timeout_fails"] = 1
    meta["meta"]["last_yahoo_inflight_fails"] = 7
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    counted = build_universe_discovery_glance(tmp_path, now=now)
    assert counted["yahoo_fail_error_also_share_pct"] == 12
    assert counted["yahoo_fail_error_also_vs_pct"] == 88
    assert counted["yahoo_fail_error_also_vs_delta_lead_size"] == (
        "Δ lead size · 7×"
    )
    assert counted["yahoo_fail_error_also_vs_delta_lead_size_x"] == 7.0
    assert "Δ lead size · 7×" in counted["mix_lean"]
    assert "6.77×" not in counted["mix_lean"]
    assert counted["yahoo_fail_error_also_vs_delta_lead_size_sides"] == (
        "Δ lead size sides · held 7 · timeout 1"
    )
    assert "Δ lead size sides · held 7 · timeout 1" in counted["mix_lean"]
    assert counted["yahoo_fail_error_also_vs_delta_lead_size_sides_share"] == (
        "Δ lead size sides share · held 88% · timeout 12%"
    )
    assert "Δ lead size sides share · held 88% · timeout 12%" in counted["mix_lean"]
    assert counted["yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta"] == (
        "Δ lead size sides share Δ wide · +76pp"
    )
    assert (
        "Δ lead size sides share Δ wide · +76pp" in counted["mix_lean"]
    )
    assert counted["yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap"] == (
        "Δ lead size sides share vs gap align · wide"
    )
    assert (
        "Δ lead size sides share vs gap align · wide" in counted["mix_lean"]
    )
    assert counted["yahoo_fail_error_also_vs_delta_lead_size_sides_delta"] == (
        "Δ lead size sides Δ wide · 6 screens"
    )
    assert "Δ lead size sides Δ wide · 6 screens" in counted["mix_lean"]
    assert half["yahoo_fail_error_also_vs_delta_lead_size_sides_delta"] == ""
    assert half["yahoo_fail_error_also_vs_delta_lead_size_sides_share"] == ""
    assert half["yahoo_fail_error_also_vs_delta_lead_size_sides_share_delta"] == ""
    assert half["yahoo_fail_error_also_vs_delta_lead_size_sides_share_vs_gap"] == ""


def test_universe_discovery_glance_yahoo_fail_error_vs_seed_first_fail(
    tmp_path,
) -> None:
    """Typed first-fail vs fresh seed — N× silent, error/seed speaks clash."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "last_yahoo_discovery_error": "timeout",
                    "yahoo_discovery_fail_streak": 1,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_fail_error"] == "timeout"
    assert g["yahoo_fail_error_vs_seed"] == "clash · fresh"
    assert g["yahoo_fail_error_vs_fail"] == "align · fresh"
    assert g["yahoo_fail_error_seed_vs_fail"] == (
        "clash · seed clash · fail align"
    )
    assert g["yahoo_fail_error_seed_vs_fail_warn"] is True
    # Fail 10m ago → still inside 1h backoff → first-fail budget held.
    assert g["yahoo_fail_error_vs_budget"] == "clash · held · not spent"
    # seed/fail clash + budget clash → error sf/budget align · both clash.
    assert g["yahoo_fail_error_seed_fail_vs_budget"] == "align · both clash"
    assert g["yahoo_fail_error_seed_fail_vs_budget_warn"] is True
    assert g["error_lean_warn"] is True
    assert g["error_lean_meta"] == "align · both clash · seed · sf/budget"
    assert "Yahoo fail · timeout · 0/3" in g["line_core"]
    assert "error/" not in g["line_core"]
    assert "error/seed clash · fresh" in g["error_lean"]
    assert "error sf/budget align · both clash" in g["error_lean"]
    # seed/fail + budget stay in fields; relationship owns the fold.
    assert "error seed/fail" not in g["error_lean"]
    assert "error seed/fail" not in g["line"]
    assert "error/budget" not in g["error_lean"]
    assert "error/budget" not in g["line"]
    assert "error/fail" not in g["error_lean"]
    assert "error sf/budget align · both clash" in g["line"]
    assert "1×" not in g["line_core"]
    assert "streak/seed" not in g["line"]
    assert "streak/fail" not in g["line"]
    # Stale seed aligns (typed death + old list; stale ≥ 2×24h throttle).
    last_stale = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["last_yahoo_discovery"] = last_stale
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    stale = build_universe_discovery_glance(tmp_path, now=now)
    assert stale["yahoo_fail_error_vs_seed"] == "align · stale"
    assert stale["yahoo_fail_error_vs_fail"] == "align · fresh"
    assert stale["yahoo_fail_error_seed_vs_fail"] == "align · both align"
    assert stale["yahoo_fail_error_seed_vs_fail_warn"] is False
    assert stale["yahoo_fail_error_vs_budget"] == "clash · held · not spent"
    assert stale["yahoo_fail_error_seed_fail_vs_budget"] == (
        "clash · seed/fail align · budget clash"
    )
    assert stale["yahoo_fail_error_seed_fail_vs_budget_warn"] is True
    assert stale["error_lean_warn"] is True
    # sf/budget clash body also names seed/fail · budget (inventory keeps both).
    assert stale["error_lean_meta"] == "clash · seed · sf/budget · seed/fail"
    assert "error/" not in stale["line_core"]
    assert "error/seed align · stale" in stale["error_lean"]
    assert "error sf/budget clash · seed/fail align · budget clash" in stale[
        "error_lean"
    ]
    assert "error seed/fail" not in stale["error_lean"]
    assert "error/budget" not in stale["error_lean"]
    assert "error/fail" not in stale["error_lean"]
    # Stale fail stamp clashes (typed death without a live death clock).
    fail_stale = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["last_yahoo_discovery_fail"] = fail_stale
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    fail_stale_g = build_universe_discovery_glance(tmp_path, now=now)
    assert fail_stale_g["yahoo_fail_error_vs_fail"] == "clash · stale"
    assert fail_stale_g["yahoo_fail_error_seed_vs_fail"] == (
        "clash · seed align · fail clash"
    )
    assert fail_stale_g["yahoo_fail_error_seed_vs_fail_warn"] is True
    # Fail 50h ago → backoff elapsed → first-fail budget about to spend.
    assert fail_stale_g["yahoo_fail_error_vs_budget"] == "align · due"
    assert fail_stale_g["yahoo_fail_error_seed_fail_vs_budget"] == (
        "clash · seed/fail clash · budget align"
    )
    assert fail_stale_g["yahoo_fail_error_seed_fail_vs_budget_warn"] is True
    assert "error/" not in fail_stale_g["line_core"]
    assert "retry due" in fail_stale_g["line_core"]
    assert "error sf/budget clash · seed/fail clash · budget align" in fail_stale_g[
        "error_lean"
    ]
    assert "error/budget" not in fail_stale_g["error_lean"]
    assert "error/fail" not in fail_stale_g["error_lean"]
    # Fresh seed + stale fail → both clash under retry-due (about to spend).
    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["last_yahoo_discovery"] = last
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    due_clash = build_universe_discovery_glance(tmp_path, now=now)
    assert due_clash["yahoo_fail_error_seed_vs_fail"] == "align · both clash"
    assert due_clash["yahoo_fail_error_vs_budget"] == "align · due"
    assert due_clash["yahoo_fail_error_seed_fail_vs_budget"] == "align · both align"
    assert due_clash["yahoo_fail_error_seed_fail_vs_budget_warn"] is True
    assert "error/" not in due_clash["line_core"]
    assert "error sf/budget align · both align" in due_clash["error_lean"]
    assert due_clash["error_lean_warn"] is True
    assert "retry due" in due_clash["line_core"]


def test_universe_discovery_glance_yahoo_fail_streak_speaks(tmp_path) -> None:
    """xang1234 #639: repeated fails speak N× (chronic dead ≠ quiet seed)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "yahoo_discovery_fail_streak": 3,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_failed"] is True
    assert g["yahoo_fail_streak"] == 3
    assert g["yahoo_fail_error"] == ""
    assert g["yahoo_fail_streak_vs_seed"] == "clash · fresh"
    assert g["yahoo_fail_streak_vs_fail"] == "align · fresh"
    # Crossed seed clash / fail align → seed/fail meta (drops streak/fail on line).
    assert g["yahoo_fail_streak_seed_vs_fail"] == (
        "clash · seed clash · fail align"
    )
    assert g["yahoo_fail_streak_seed_vs_fail_warn"] is True
    # Fail 10m ago → still inside 1h backoff → budget held (xang1234 #640).
    assert g["yahoo_fail_streak_vs_budget"] == "clash · held · not spent"
    # seed/fail clash + budget clash → sf/budget align · both clash.
    assert g["yahoo_fail_streak_seed_fail_vs_budget"] == "align · both clash"
    assert g["yahoo_fail_streak_seed_fail_vs_budget_warn"] is True
    assert "streak/seed clash · fresh" in g["line"]
    assert "seed/fail clash · seed clash · fail align" in g["line"]
    assert "streak/fail" not in g["line"]  # dropped when meta spoke; stays in fields
    assert "sf/budget align · both clash" in g["line"]
    assert "streak/budget" not in g["line"]  # dropped when sf/budget spoke
    assert g["line"].index("3×") < g["line"].index("streak/seed")
    assert g["line"].index("streak/seed") < g["line"].index("seed/fail")
    assert g["line"].index("seed/fail") < g["line"].index("sf/budget")
    assert g["line"].index("sf/budget") < g["line"].index("retry")
    # MonsterDeveloper fold: primary keeps fail · N× · retry; lean owns cascade.
    assert "3×" in g["line_core"]
    assert "retry" in g["line_core"]
    assert "streak/seed" not in g["line_core"]
    assert "sf/budget" not in g["line_core"]
    assert "streak/seed clash · fresh" in g["streak_lean"]
    assert "sf/budget align · both clash" in g["streak_lean"]
    assert g["streak_lean_warn"] is True
    assert g["streak_lean_meta"] == (
        "align · both clash · seed · seed/fail · sf/budget"
    )


def test_universe_discovery_glance_yahoo_fail_lean_quiet_inventory(
    tmp_path,
) -> None:
    """Calm error/streak folds name spoken stages (not a static cascade)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_error": "timeout",
                    "yahoo_discovery_fail_streak": 1,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["error_lean_warn"] is False
    assert "error/seed clash · fresh" in g["error_lean"]
    assert "error/budget align · due" in g["error_lean"]
    assert g["error_lean_meta"] == "quiet · 2 folds · seed · budget"
    meta = json.loads((tmp_path / "stock_universe.json").read_text(encoding="utf-8"))
    meta["meta"]["yahoo_discovery_fail_streak"] = 3
    meta["meta"].pop("last_yahoo_discovery_error", None)
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    streak = build_universe_discovery_glance(tmp_path, now=now)
    assert streak["streak_lean_warn"] is False
    assert "streak/seed clash · fresh" in streak["streak_lean"]
    assert "streak/budget align · due" in streak["streak_lean"]
    assert streak["streak_lean_meta"] == "quiet · 2 folds · seed · budget"


def test_universe_discovery_glance_yahoo_fail_streak_vs_seed_stale(
    tmp_path,
) -> None:
    """Hot streak + stale seed speaks align (both adverse)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    # >48h with 24h throttle → stale
    last = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "yahoo_discovery_fail_streak": 4,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["seed_freshness"] == "stale"
    assert g["yahoo_fail_streak_vs_seed"] == "align · stale"
    assert g["yahoo_fail_streak_vs_fail"] == "align · fresh"
    assert g["yahoo_fail_streak_seed_vs_fail"] == "align · both align"
    assert g["yahoo_fail_streak_seed_vs_fail_warn"] is False
    # Fail 10m ago → budget held; seed/fail both-align vs budget clash → crossed.
    assert g["yahoo_fail_streak_vs_budget"] == "clash · held · not spent"
    assert g["yahoo_fail_streak_seed_fail_vs_budget"] == (
        "clash · seed/fail align · budget clash"
    )
    assert g["yahoo_fail_streak_seed_fail_vs_budget_warn"] is True
    assert "streak/seed align · stale" in g["line"]
    assert "seed/fail align · both align" in g["line"]
    assert "streak/fail" not in g["line"]
    assert "sf/budget clash · seed/fail align · budget clash" in g["line"]
    assert "streak/budget" not in g["line"]
    assert "streak/seed" not in g["line_core"]
    assert "sf/budget clash · seed/fail align · budget clash" in g["streak_lean"]
    assert g["streak_lean_warn"] is True


def test_universe_discovery_glance_yahoo_fail_streak_vs_fail_stale(
    tmp_path,
) -> None:
    """Hot streak + stale fail stamp speaks clash (counter ≠ live death)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    # >48h with 24h throttle → stale fail stamp
    fail = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "yahoo_discovery_fail_streak": 5,
                    "last_yahoo_screens_ok": 0,
                    "last_yahoo_screens_failed": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["fail_freshness"] == "stale"
    assert g["yahoo_fail_streak_vs_seed"] == "clash · fresh"
    assert g["yahoo_fail_streak_vs_fail"] == "clash · stale"
    assert g["yahoo_fail_streak_seed_vs_fail"] == "align · both clash"
    assert g["yahoo_fail_streak_seed_vs_fail_warn"] is True
    # Fail 50h ago → backoff elapsed → budget about to spend (xang1234 #640).
    assert g["yahoo_fail_streak_vs_budget"] == "align · due"
    # Outer both-align but seed/fail dual-clash under due → warn
    # (soft-allow both-clash parity; about-to-spend ≠ quiet confirm).
    assert g["yahoo_fail_streak_seed_fail_vs_budget"] == "align · both align"
    assert g["yahoo_fail_streak_seed_fail_vs_budget_warn"] is True
    assert "seed/fail align · both clash" in g["line"]
    assert "streak/fail" not in g["line"]
    assert "sf/budget align · both align" in g["line"]
    assert "streak/budget" not in g["line"]
    assert g["line"].index("seed/fail") < g["line"].index("sf/budget")
    assert g["line"].index("sf/budget") < g["line"].index("retry")
    assert "retry due" in g["line_core"]
    assert "seed/fail" not in g["line_core"]
    assert "seed/fail align · both clash" in g["streak_lean"]
    assert "sf/budget align · both align" in g["streak_lean"]
    assert g["streak_lean_warn"] is True


def test_universe_discovery_glance_yahoo_fail_shows_screen_fraction(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_added": 2,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_screens_ok": 1,
                    "last_yahoo_screens_failed": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["tone"] == "warn"
    assert g["screens_bit"] == "1/3"
    assert g["seed_freshness"] == "fresh"
    assert "Yahoo fail · 1/3" in g["line"]
    assert "seed 6h ago · fresh" in g["line"]
    assert "retry due" in g["line"]
    assert g["yahoo_retry_due"] is True


def test_universe_discovery_glance_yahoo_fail_stale_seed(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["tone"] == "warn"
    assert g["seed_freshness"] == "stale"
    assert g["yahoo_retry_due"] is True
    assert "seed 2d ago · stale" in g["line"]
    assert "retry due" in g["line"]
    assert g["fail_freshness"] == "never"
    assert g["seed_vs_fail"] == ""
    assert "fail fresh" not in g["line"]
    assert "fail aging" not in g["line"]
    assert "fail stale" not in g["line"]
    assert "seed lags" not in g["line"]
    assert "fail lags" not in g["line"]


def test_universe_discovery_glance_yahoo_fail_age_bands(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    seed = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()

    def _write(fail_hours: float) -> None:
        fail = (now - timedelta(hours=fail_hours)).replace(tzinfo=None).isoformat()
        (tmp_path / "stock_universe.json").write_text(
            json.dumps(
                {
                    "stocks": {"AAPL": {}},
                    "meta": {
                        "last_yahoo_discovery": seed,
                        "last_yahoo_discovery_status": "failed",
                        "last_yahoo_discovery_fail": fail,
                    },
                }
            ),
            encoding="utf-8",
        )

    _write(6)
    fresh = build_universe_discovery_glance(tmp_path, now=now)
    assert fresh["fail_freshness"] == "fresh"
    assert fresh["fail_age_sec"] == 6 * 3600
    assert fresh["fail_age_label"] == "6h ago"
    assert "fail 6h ago · fresh" in fresh["line"]
    assert "seed 6h ago · fresh" in fresh["line"]
    assert "retry due" in fresh["line"]

    _write(30)
    aging = build_universe_discovery_glance(tmp_path, now=now)
    assert aging["fail_freshness"] == "aging"
    assert aging["fail_age_label"] == "30h ago"
    assert "fail 30h ago · aging" in aging["line"]
    assert "seed 6h ago · fresh" in aging["line"]
    assert aging["seed_vs_fail"] == "fail lags"
    assert "fail lags" in aging["line"]
    # |30h−6h| = 24h → wide (≥ throttle)
    assert aging["seed_vs_fail_delta_sec"] == 24 * 3600
    assert aging["seed_vs_fail_delta_label"] == "24h"
    assert aging["seed_vs_fail_delta_severity"] == "wide"
    assert aging["seed_vs_fail_lean_vs_delta"] == "align"
    assert "Δ wide · 24h" in aging["line"]
    assert " · align" in aging["line"]
    assert aging["tone"] == "warn"

    _write(50)
    stale = build_universe_discovery_glance(tmp_path, now=now)
    assert stale["fail_freshness"] == "stale"
    assert stale["fail_age_label"] == "2d ago"
    assert "fail 2d ago · stale" in stale["line"]
    assert "seed 6h ago · fresh" in stale["line"]
    # seed fresh + fail stale → fail is the older band
    assert stale["seed_vs_fail"] == "fail lags"
    assert "fail lags" in stale["line"]
    assert "seed lags" not in stale["line"]
    # |50h−6h| = 44h → wide · 1d
    assert stale["seed_vs_fail_delta_sec"] == 44 * 3600
    assert stale["seed_vs_fail_delta_label"] == "1d"
    assert stale["seed_vs_fail_delta_severity"] == "wide"
    assert stale["seed_vs_fail_lean_vs_delta"] == "align"
    assert "Δ wide · 1d" in stale["line"]
    assert " · align" in stale["line"]

    _write(6)
    aligned = build_universe_discovery_glance(tmp_path, now=now)
    assert aligned["seed_vs_fail"] == ""
    assert aligned["seed_vs_fail_delta_severity"] == ""
    assert aligned["seed_vs_fail_lean_vs_delta"] == ""
    assert "seed lags" not in aligned["line"]
    assert "fail lags" not in aligned["line"]
    assert "Δ wide" not in aligned["line"]
    assert "Δ thin" not in aligned["line"]
    assert "lean vs Δ clash" not in aligned["line"]
    assert " · align" not in aligned["line"]


def test_universe_discovery_glance_yahoo_fail_seed_lags(tmp_path) -> None:
    """Seed older than fail → seed lags (speak-both-sides; display only)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    seed = (now - timedelta(hours=50)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": seed,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["seed_freshness"] == "stale"
    assert g["fail_freshness"] == "fresh"
    assert g["seed_vs_fail"] == "seed lags"
    assert "seed 2d ago · stale" in g["line"]
    assert "fail 6h ago · fresh" in g["line"]
    assert "seed lags" in g["line"]
    assert "fail lags" not in g["line"]
    assert g["seed_vs_fail_delta_severity"] == "wide"
    assert g["seed_vs_fail_delta_label"] == "1d"
    assert g["seed_vs_fail_lean_vs_delta"] == "align"
    assert "Δ wide · 1d" in g["line"]
    assert " · align" in g["line"]
    assert "retry due" in g["line"]


def test_universe_discovery_glance_yahoo_fail_retry_backoff(tmp_path) -> None:
    """Fail backoff: speak retry in Nm while cooling (xang1234 dfb6a86)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    seed = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(minutes=15)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": seed,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_failed"] is True
    assert g["yahoo_retry_due"] is False
    assert g["yahoo_retry_remain_sec"] == 45 * 60
    assert g["yahoo_fail_backoff_hours"] == 1
    assert "retry in 45m" in g["line"]
    assert "retry due" not in g["line"]
    assert "seed 6h ago · fresh" in g["line"]
    assert "fail 15m ago · fresh" in g["line"]
    # Retry before seed ages — thrash-calm bit is not last.
    assert g["line"].index("retry in 45m") < g["line"].index("seed 6h ago")


def test_universe_discovery_glance_yahoo_fail_retry_survives_long_lag(
    tmp_path,
) -> None:
    """Long seed/fail lag must not clip retry due (xang1234 never-partial)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    seed = (now - timedelta(hours=23)).replace(tzinfo=None).isoformat()
    fail = (now - timedelta(hours=40)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": seed,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": fail,
                    "last_yahoo_screens_ok": 1,
                    "last_yahoo_screens_failed": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_failed"] is True
    assert g["yahoo_retry_due"] is True
    assert "retry due" in g["line"]
    assert not g["line"].endswith("…")
    assert "Yahoo fail · 1/3 · retry due" in g["line"]
    # Lag still speaks when the fail-path budget fits.
    assert "lean vs Δ clash · mid · 17h" in g["line"]
    assert g["line"].index("retry due") < g["line"].index("fail lags")


def test_universe_discovery_glance_yahoo_fail_lag_delta_thin_mid(tmp_path) -> None:
    """Lag Δ thin near band edge; mid gap speaks lean vs Δ clash (display only)."""
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)

    def _write(seed_h: float, fail_h: float) -> dict:
        seed = (now - timedelta(hours=seed_h)).replace(tzinfo=None).isoformat()
        fail = (now - timedelta(hours=fail_h)).replace(tzinfo=None).isoformat()
        (tmp_path / "stock_universe.json").write_text(
            json.dumps(
                {
                    "stocks": {"AAPL": {}},
                    "meta": {
                        "last_yahoo_discovery": seed,
                        "last_yahoo_discovery_status": "failed",
                        "last_yahoo_discovery_fail": fail,
                    },
                }
            ),
            encoding="utf-8",
        )
        return build_universe_discovery_glance(tmp_path, now=now)

    # seed 23h fresh · fail 25h aging → lag · Δ thin · 2h (< ½ throttle)
    thin = _write(23, 25)
    assert thin["seed_freshness"] == "fresh"
    assert thin["fail_freshness"] == "aging"
    assert thin["seed_vs_fail"] == "fail lags"
    assert thin["seed_vs_fail_delta_sec"] == 2 * 3600
    assert thin["seed_vs_fail_delta_label"] == "2h"
    assert thin["seed_vs_fail_delta_severity"] == "thin"
    assert thin["seed_vs_fail_lean_vs_delta"] == "align"
    assert "fail lags" in thin["line"]
    assert "Δ thin · 2h" in thin["line"]
    assert " · align" in thin["line"]
    assert "lean vs Δ clash" not in thin["line"]

    # seed 23h fresh · fail 40h aging → lag · gap 17h mid → lean vs Δ clash
    # (still speak 17h — never-partial mid gap; severity stays silent)
    mid = _write(23, 40)
    assert mid["seed_freshness"] == "fresh"
    assert mid["fail_freshness"] == "aging"
    assert mid["seed_vs_fail"] == "fail lags"
    assert mid["seed_vs_fail_delta_sec"] == 17 * 3600
    assert mid["seed_vs_fail_delta_label"] == "17h"
    assert mid["seed_vs_fail_delta_severity"] == ""
    assert mid["seed_vs_fail_lean_vs_delta"] == "clash"
    assert "fail lags" in mid["line"]
    assert "lean vs Δ clash · mid · 17h" in mid["line"]
    assert "Δ wide" not in mid["line"]
    assert "Δ thin" not in mid["line"]
    assert " · align" not in mid["line"]


def test_universe_discovery_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    last = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps({"meta": {"last_yahoo_discovery": last, "last_yahoo_added": 0}}),
        encoding="utf-8",
    )
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["universe_discovery_glance"]
    assert g["ready"] is True
    assert g["tone"] == "fresh"
    assert "cache" in g["line"]
    assert g["auto_buy"] is False


def test_universe_discovery_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["universe_discovery_glance"]
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert "cache never" in g["line"]


def test_universe_discovery_glance_dropped_movers_on_success(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_added": 1,
                    "last_yahoo_dropped": 4,
                    "last_yahoo_discovery_status": "ok",
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["last_yahoo_dropped"] == 4
    assert g["last_yahoo_dropped_venue"] is None
    assert "dropped 4 · US" in g["line"]
    assert g["tone"] == "fresh"


def test_universe_discovery_glance_dropped_movers_speaks_venue(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_added": 1,
                    "last_yahoo_dropped": 2,
                    "last_yahoo_dropped_venue": "US",
                    "last_yahoo_discovery_status": "ok",
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["last_yahoo_dropped_venue"] == "US"
    assert "dropped 2 · US" in g["line"]


def test_universe_discovery_glance_partial_skip_prune(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_added": 1,
                    "last_yahoo_dropped": 0,
                    "last_yahoo_prune_skipped": True,
                    "last_yahoo_screens_ok": 2,
                    "last_yahoo_screens_failed": 1,
                    "last_yahoo_discovery_status": "ok",
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["last_yahoo_prune_skipped"] is True
    assert g["tone"] == "fresh"
    assert "partial · skip prune" in g["line"]
    assert "dropped" not in g["line"]
    assert "discovery-only" in g["line"]


def test_universe_discovery_glance_fail_path_hides_dropped(tmp_path) -> None:
    now = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=6)).replace(tzinfo=None).isoformat()
    (tmp_path / "stock_universe.json").write_text(
        json.dumps(
            {
                "stocks": {"AAPL": {}},
                "meta": {
                    "last_yahoo_discovery": last,
                    "last_yahoo_discovery_status": "failed",
                    "last_yahoo_discovery_fail": last,
                    "last_yahoo_dropped": 4,
                },
            }
        ),
        encoding="utf-8",
    )
    g = build_universe_discovery_glance(tmp_path, now=now)
    assert g["yahoo_failed"] is True
    assert g["last_yahoo_dropped"] == 4
    assert "dropped 4" not in g["line"]
    assert "Yahoo fail" in g["line"]
