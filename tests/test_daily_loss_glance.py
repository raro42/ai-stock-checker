"""UTC-day daily loss halt glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    DAILY_LOSS_LINE_CHARS,
    _clip_daily_loss_line,
    _coerce_daily_loss_line_chars,
    build_daily_loss_glance,
    load_desk_snapshot,
)


def test_daily_loss_glance_empty_without_capital() -> None:
    g = build_daily_loss_glance(0.0, 0.0)
    assert g["ready"] is False


def test_daily_loss_glance_refuses_bool_pnl_capital_threshold() -> None:
    """tradermonty #700/#655: True→€1 PnL / €1 start / 1% halt must not invent."""
    assert build_daily_loss_glance(True, 100_000.0)["ready"] is False  # type: ignore[arg-type]
    assert build_daily_loss_glance(-100.0, True)["ready"] is False  # type: ignore[arg-type]
    assert build_daily_loss_glance(False, 100_000.0)["ready"] is False  # type: ignore[arg-type]
    # Damaged threshold falls back to default 2% (not invent "off" from False).
    g = build_daily_loss_glance(50.0, 100_000.0, threshold_pct=False)  # type: ignore[arg-type]
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["threshold_pct"] == 2.0
    assert "−2%" in g["line"] or "-2%" in g["line"]


def test_daily_loss_glance_clear() -> None:
    g = build_daily_loss_glance(50.0, 100_000.0)
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["halted"] is False
    assert "clear" in g["line"]
    assert "−2%" in g["line"] or "-2%" in g["line"]


def test_daily_loss_glance_warn_under_halt() -> None:
    g = build_daily_loss_glance(-800.0, 100_000.0)
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["halted"] is False
    assert "UTC day" in g["line"]
    assert "halt at" in g["line"]


def test_daily_loss_glance_halted() -> None:
    g = build_daily_loss_glance(-2_500.0, 100_000.0)
    assert g["ready"] is True
    assert g["tone"] == "halt"
    assert g["halted"] is True
    assert "HALT" in g["line"]
    assert "buys blocked" in g["line"]


def test_daily_loss_glance_off() -> None:
    g = build_daily_loss_glance(-100.0, 100_000.0, threshold_pct=0)
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "off" in g["line"]


def test_daily_loss_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["daily_loss_glance"]
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert "halt at" in g["line"]


def test_daily_loss_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    payload = load_chart_payload(tmp_path)
    g = payload["daily_loss_glance"]
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert "halt at" in g["line"]


def test_clip_daily_loss_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > DAILY_LOSS_LINE_CHARS
    default = _clip_daily_loss_line(long)
    assert len(default) == DAILY_LOSS_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: DAILY_LOSS_LINE_CHARS - 1] + "…"
    assert _clip_daily_loss_line(long, True) == default
    assert _clip_daily_loss_line(long, False) == default
    assert _clip_daily_loss_line(long, 0) == default
    assert _coerce_daily_loss_line_chars(True) == DAILY_LOSS_LINE_CHARS
    assert _coerce_daily_loss_line_chars(False) == DAILY_LOSS_LINE_CHARS
    thin = _clip_daily_loss_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_daily_loss_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    g = build_daily_loss_glance(50.0, 100_000.0)
    g_bool = build_daily_loss_glance(50.0, 100_000.0, line_n=True)
    g_false = build_daily_loss_glance(50.0, 100_000.0, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= DAILY_LOSS_LINE_CHARS
    g_short = build_daily_loss_glance(50.0, 100_000.0, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")
