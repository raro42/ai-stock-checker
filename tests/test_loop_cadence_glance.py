"""Loop cadence honesty glance (scan/trade floors; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    LOOP_CADENCE_LINE_CHARS,
    LOOP_CADENCE_SCAN_FLOOR_MIN,
    LOOP_CADENCE_TRADE_FLOOR_MIN,
    _clip_loop_cadence_line,
    _coerce_loop_cadence_line_chars,
    build_loop_cadence_glance,
    load_desk_snapshot,
)


def test_loop_cadence_glance_empty() -> None:
    assert build_loop_cadence_glance(None)["ready"] is False
    assert build_loop_cadence_glance({})["ready"] is False
    assert build_loop_cadence_glance({"scan_interval_min": 15})["ready"] is False


def test_loop_cadence_glance_refuses_bool_intervals() -> None:
    """tradermonty #700/#655: True→1m must not invent a live scan/trade cadence."""
    assert (
        build_loop_cadence_glance(
            {"scan_interval_min": True, "trade_interval_min": 5}
        )["ready"]
        is False
    )
    assert (
        build_loop_cadence_glance(
            {"scan_interval_min": 15, "trade_interval_min": True}
        )["ready"]
        is False
    )
    assert (
        build_loop_cadence_glance(
            {"scan_interval_min": False, "trade_interval_min": False}
        )["ready"]
        is False
    )


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


def test_loop_cadence_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["loop_cadence_glance"]
    assert g["ready"] is True
    assert g["tone"] == "ok"
    assert "scan 15m" in g["line"]
    assert "trade 5m" in g["line"]


def test_clip_loop_cadence_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > LOOP_CADENCE_LINE_CHARS
    default = _clip_loop_cadence_line(long)
    assert len(default) == LOOP_CADENCE_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: LOOP_CADENCE_LINE_CHARS - 1] + "…"
    assert _clip_loop_cadence_line(long, True) == default
    assert _clip_loop_cadence_line(long, False) == default
    assert _clip_loop_cadence_line(long, 0) == default
    assert _coerce_loop_cadence_line_chars(True) == LOOP_CADENCE_LINE_CHARS
    assert _coerce_loop_cadence_line_chars(False) == LOOP_CADENCE_LINE_CHARS
    thin = _clip_loop_cadence_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_loop_cadence_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    rt = {"scan_interval_min": 15, "trade_interval_min": 5}
    g = build_loop_cadence_glance(rt)
    g_bool = build_loop_cadence_glance(rt, line_n=True)
    g_false = build_loop_cadence_glance(rt, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= LOOP_CADENCE_LINE_CHARS
    assert "scan 15m" in g["line"]
