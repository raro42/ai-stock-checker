"""Loop cadence honesty glance (scan/trade floors; display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    LOOP_CADENCE_SCAN_FLOOR_MIN,
    LOOP_CADENCE_TRADE_FLOOR_MIN,
    build_loop_cadence_glance,
    load_desk_snapshot,
)


def test_loop_cadence_glance_empty() -> None:
    assert build_loop_cadence_glance(None)["ready"] is False
    assert build_loop_cadence_glance({})["ready"] is False
    assert build_loop_cadence_glance({"scan_interval_min": 15})["ready"] is False


def test_loop_cadence_glance_ok() -> None:
    g = build_loop_cadence_glance(
        {"scan_interval_min": 15, "trade_interval_min": 5}
    )
    assert g["ready"] is True
    assert g["tone"] == "ok"
    assert g["below_floor"] is False
    assert g["scan_min"] == 15
    assert g["trade_min"] == 5
    assert g["scan_floor_min"] == LOOP_CADENCE_SCAN_FLOOR_MIN
    assert g["trade_floor_min"] == LOOP_CADENCE_TRADE_FLOOR_MIN
    assert "scan 15m" in g["line"]
    assert "trade 5m" in g["line"]
    assert "floors ≥15m/≥5m" in g["line"]
    assert "below" not in g["line"]


def test_loop_cadence_glance_below_scan_floor() -> None:
    g = build_loop_cadence_glance(
        {"scan_interval_min": 5, "trade_interval_min": 5}
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["below_floor"] is True
    assert "below floors" in g["line"]


def test_loop_cadence_glance_below_trade_floor() -> None:
    g = build_loop_cadence_glance(
        {"scan_interval_min": 15, "trade_interval_min": 1}
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["below_floor"] is True
    assert "trade 1m" in g["line"]


def test_loop_cadence_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["loop_cadence_glance"]
    assert g["ready"] is True
    assert g["tone"] == "ok"
    assert "scan 15m" in g["line"]
    assert "trade 5m" in g["line"]
