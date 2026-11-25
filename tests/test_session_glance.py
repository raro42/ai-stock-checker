"""UTC session / weekend policy glance (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    SESSION_LINE_CHARS,
    _clip_session_line,
    _coerce_session_line_chars,
    build_session_glance,
    load_desk_snapshot,
)


def test_session_glance_weekday_explicit() -> None:
    g = build_session_glance(weekend=False)
    assert g["ready"] is True
    assert g["tone"] == "weekday"
    assert g["weekend_mode"] is False
    assert "weekday" in g["line"]
    assert "stocks + crypto" in g["line"]


def test_session_glance_weekend_explicit() -> None:
    g = build_session_glance(weekend=True)
    assert g["ready"] is True
    assert g["tone"] == "weekend"
    assert g["weekend_mode"] is True
    assert "crypto-only" in g["line"]
    assert "stocks paused" in g["line"]


def test_coerce_session_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char Session strip; False must not wipe."""
    assert _coerce_session_line_chars(True) == SESSION_LINE_CHARS
    assert _coerce_session_line_chars(False) == SESSION_LINE_CHARS
    assert _coerce_session_line_chars(0) == SESSION_LINE_CHARS
    assert _coerce_session_line_chars(None) == SESSION_LINE_CHARS
    assert _coerce_session_line_chars(40) == 40


def test_clip_session_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > SESSION_LINE_CHARS
    default = _clip_session_line(long)
    assert len(default) == SESSION_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: SESSION_LINE_CHARS - 1] + "…"
    assert _clip_session_line(long, True) == default
    assert _clip_session_line(long, False) == default
    assert _clip_session_line(long, 0) == default
    thin = _clip_session_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_session_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_session_glance(weekend=False)
    g_bool = build_session_glance(weekend=False, line_n=True)
    g_false = build_session_glance(weekend=False, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= SESSION_LINE_CHARS
    g_short = build_session_glance(weekend=False, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_session_glance_from_utc_saturday() -> None:
    sat = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)  # Saturday
    g = build_session_glance(now=sat)
    assert g["weekend_mode"] is True
    assert g["tone"] == "weekend"


def test_session_glance_from_utc_wednesday() -> None:
    wed = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)  # Wednesday
    g = build_session_glance(now=wed)
    assert g["weekend_mode"] is False
    assert g["tone"] == "weekday"


def test_session_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["session_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"weekday", "weekend"}
    assert g["weekend_mode"] is bool(snap["weekend_mode"])
    assert g["line"]


def test_session_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["session_glance"]
    assert g["ready"] is True
    assert g["tone"] in {"weekday", "weekend"}
    assert g["line"]
