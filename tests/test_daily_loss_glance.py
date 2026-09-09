"""UTC-day daily loss halt glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_daily_loss_glance, load_desk_snapshot


def test_daily_loss_glance_empty_without_capital() -> None:
    g = build_daily_loss_glance(0.0, 0.0)
    assert g["ready"] is False


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
