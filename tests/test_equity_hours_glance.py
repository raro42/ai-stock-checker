"""US RTH vs Xetra equity-hours honesty glance (display only)."""

from __future__ import annotations

from datetime import datetime

import pytz

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_equity_hours_glance, load_desk_snapshot


def test_equity_hours_glance_both_open_us_morning() -> None:
    # Wednesday 10:00 ET ≈ both US RTH and Xetra open (Xetra until 17:30 Berlin).
    now = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    assert g["ready"] is True
    assert g["tone"] == "open"
    assert g["us_open"] is True
    assert g["xetra_open"] is True
    assert "US RTH open" in g["line"]
    assert "Xetra open" in g["line"]
    assert "crypto 24/7" in g["line"]


def test_equity_hours_glance_both_closed_weekend() -> None:
    sat = pytz.timezone("US/Eastern").localize(datetime(2026, 9, 12, 12, 0))
    g = build_equity_hours_glance(now=sat)
    assert g["ready"] is True
    assert g["tone"] == "closed"
    assert g["us_open"] is False
    assert g["xetra_open"] is False
    assert "US RTH closed" in g["line"]
    assert "Xetra closed" in g["line"]


def test_equity_hours_glance_split_xetra_only() -> None:
    # 10:00 Berlin weekday: Xetra open; US still closed (04:00 ET).
    now = pytz.timezone("Europe/Berlin").localize(datetime(2026, 9, 9, 10, 0))
    g = build_equity_hours_glance(now=now)
    assert g["ready"] is True
    assert g["tone"] == "split"
    assert g["xetra_open"] is True
    assert g["us_open"] is False
    assert "Xetra open" in g["line"]
    assert "US RTH closed" in g["line"]


def test_equity_hours_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["equity_hours_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"open", "closed", "split"}
    assert "US RTH" in g["line"]
    assert "Xetra" in g["line"]
    assert "crypto 24/7" in g["line"]


def test_equity_hours_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["equity_hours_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"open", "closed", "split"}
    assert "US RTH" in g["line"]
    assert "Xetra" in g["line"]
    assert "crypto 24/7" in g["line"]
