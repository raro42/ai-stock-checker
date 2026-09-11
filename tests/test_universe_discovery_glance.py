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
    assert g["age_sec"] == 6 * 3600
    assert "cache 6h ago" in g["line"]
    assert "fresh" in g["line"]


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
