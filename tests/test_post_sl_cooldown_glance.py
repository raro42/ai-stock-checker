"""Post stop-loss buy cooldown glance (display only)."""

from __future__ import annotations

from datetime import datetime, timezone

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_post_sl_cooldown_glance, load_desk_snapshot
from stock_checker.risk_halts import (
    latest_stop_loss_sell,
    post_sl_buy_block_until,
    pretrade_status,
)


def test_post_sl_glance_clear_without_sl() -> None:
    g = build_post_sl_cooldown_glance(None, None, now=1_000_000.0)
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["active"] is False
    assert "no recent SL" in g["line"]
    assert "4h" in g["line"]


def test_post_sl_glance_off() -> None:
    g = build_post_sl_cooldown_glance("AAPL", 1.0, cooldown_seconds=0)
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "off" in g["line"]


def test_post_sl_glance_active() -> None:
    now = 1_000_000.0
    g = build_post_sl_cooldown_glance(
        "expe",
        now - 1800.0,
        cooldown_seconds=14_400.0,
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "active"
    assert g["active"] is True
    assert g["symbol"] == "EXPE"
    assert "ACTIVE" in g["line"]
    assert "EXPE" in g["line"]
    assert "buys blocked" in g["line"]


def test_post_sl_glance_expired() -> None:
    now = 1_000_000.0
    g = build_post_sl_cooldown_glance(
        "NTRA",
        now - 20_000.0,
        cooldown_seconds=14_400.0,
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["active"] is False
    assert "clear" in g["line"]
    assert "NTRA" in g["line"]


def test_latest_stop_loss_sell_and_pretrade(tmp_path) -> None:
    ts = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc).isoformat()
    (tmp_path / "trades.jsonl").write_text(
        '{"type":"SELL","symbol":"EXPE","exit_reason":"sl",'
        f'"timestamp":"{ts}","profit_loss":-50}}\n',
        encoding="utf-8",
    )
    hit = latest_stop_loss_sell(tmp_path)
    assert hit is not None
    assert hit[0] == "EXPE"
    until = post_sl_buy_block_until(tmp_path)
    assert until == hit[1] + 14_400.0
    # Still inside cooldown window relative to SL timestamp.
    level, notes = pretrade_status(
        tmp_path,
        initial_cash=100_000.0,
        now=hit[1] + 60.0,
    )
    assert level == "WARN"
    assert any("post-SL" in n for n in notes)


def test_post_sl_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["post_sl_cooldown_glance"]
    assert g["ready"] is True
    assert "SL" in g["line"] or "sl" in g["line"].lower()


def test_post_sl_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    payload = load_chart_payload(tmp_path)
    g = payload["post_sl_cooldown_glance"]
    assert g["ready"] is True
    assert g["tone"] == "clear"
