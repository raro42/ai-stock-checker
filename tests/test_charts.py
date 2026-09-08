#!/usr/bin/env python3
"""Offline tests for desk chart series."""

import json
from pathlib import Path

from openbb_backend.charts import build_equity_curve, load_chart_payload


def _seed(data: Path) -> None:
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 80000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 1,
            }
        )
    )
    (data / "trades.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-20 10:00:00",
                "type": "BUY",
                "symbol": "AAPL",
                "quantity": 10,
                "price": 100,
                "commission": 1,
                "cash_remaining": 89999,
            }
        )
        + "\n"
    )
    (data / "archive").mkdir(parents=True, exist_ok=True)
    (data / "archive" / "opportunities_latest.json").write_text("{}")


def test_equity_curve_from_fills(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    pts = build_equity_curve(tmp_path)
    assert len(pts) >= 2
    assert pts[0]["equity"] == 100000
    assert pts[1]["label"].startswith("BUY")


def test_chart_payload_offline(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    assert "equity" in payload and "allocation" in payload
    assert "from_buy" in payload
    assert "breadth_glance" in payload
    assert payload["breadth_glance"]["ready"] is False
    assert "scan_freshness" in payload
    assert payload["scan_freshness"]["ready"] is False
    assert "soft_allow_glance" in payload
    assert payload["soft_allow_glance"]["ready"] is False
    assert "book_risk_glance" in payload
    assert payload["book_risk_glance"]["ready"] is True
    assert payload["book_risk_glance"]["posture"] == "open"
    assert "1/5" in payload["book_risk_glance"]["slots"]
    assert "pretrade_glance" in payload
    assert payload["pretrade_glance"]["ready"] is True
    assert payload["pretrade_glance"]["level"] == "PASS"
    assert "next_buy_glance" in payload
    assert payload["next_buy_glance"]["ready"] is True
    assert payload["next_buy_glance"]["tone"] == "open"
    assert "Next buy" in payload["next_buy_glance"]["line"]
    assert "entry_gates_glance" in payload
    assert payload["entry_gates_glance"]["ready"] is True
    assert payload["entry_gates_glance"]["tone"] == "strict"
    assert "regime on" in payload["entry_gates_glance"]["line"]
    assert "calm_streak_glance" in payload
    assert payload["calm_streak_glance"]["ready"] is True
    assert "0/30" in payload["calm_streak_glance"]["line"]
    assert "promote_ab_glance" in payload
    assert payload["promote_ab_glance"]["ready"] is True
    assert "Window" in payload["promote_ab_glance"]["line"]
    assert "fee_burn_glance" in payload
    assert payload["fee_burn_glance"]["ready"] is True
    assert payload["fee_burn_glance"]["tone"] == "quiet"
    assert "€1.00 fees" in payload["fee_burn_glance"]["line"]
    assert "postmortem_glance" in payload
    assert payload["postmortem_glance"]["ready"] is False
    assert any(a["symbol"] == "CASH" for a in payload["allocation"])
    assert any(a["symbol"] == "AAPL" for a in payload["allocation"])


def test_chart_payload_entry_gates_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "regime_gate": True,
                "rs_gate": False,
                "breadth_gate": True,
                "promote_experiment_strategy": True,
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["entry_gates_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "mixed"
    assert glance["regime"] is True
    assert glance["rs"] is False
    assert glance["breadth"] is True
    assert glance["promote"] is True
    assert "RS off" in glance["line"]


def test_chart_payload_calm_streak_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "paper_calm.json").write_text(
        json.dumps(
            {
                "streak_days": 12,
                "required_days": 30,
                "ready_for_compose_default": False,
                "detail": "fee quiet",
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["calm_streak_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "progress"
    assert glance["streak"] == 12
    assert glance["required"] == 30
    assert "12/30" in glance["line"]
    assert "building" in glance["line"]
    assert "fee quiet" in glance["line"]



def test_chart_payload_promote_ab_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"promote_experiment_strategy": True})
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["promote_ab_glance"]
    assert glance["ready"] is True
    assert glance["promote_on"] is True
    assert glance["protocol_ok"] is False
    assert glance["tone"] == "warn"
    assert "Window A" in glance["line"]
    assert "promote on" in glance["line"]


def test_chart_payload_fee_burn_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 8000,
                "holdings": {"AAPL": 10},
                "avg_buy_price": {"AAPL": 100},
                "total_fees_paid": 250,
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["fee_burn_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "warn"
    assert glance["high"] is True
    assert "2.5%" in glance["line"]
    assert "high" in glance["line"]


def test_chart_payload_stuck_capital_glance(tmp_path: Path, monkeypatch):
    import time

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    now = 1_700_000_000.0
    monkeypatch.setattr(time, "time", lambda: now)
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 5000,
                "holdings": {"EXPE": 10},
                "avg_buy_price": {"EXPE": 100},
                "total_fees_paid": 0,
            }
        )
    )
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"EXPE": now - 48 * 3600})
    )
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"min_hold_hours": 24})
    )
    arch = tmp_path / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "stock_breakouts": [
                    {"symbol": "EXPE", "price": 92.0, "pct_from_high": 0.05}
                ]
            }
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["stuck_capital_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "warn"
    assert glance["count"] == 1
    assert "EXPE" in glance["line"]
    assert "past min-hold underwater" in glance["line"]




def test_chart_payload_next_buy_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    glance = payload["next_buy_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "open"
    assert glance["eur"] > 0
    assert glance["slots_open"] == 4
    assert "Next buy" in glance["line"]


def test_chart_payload_postmortem_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-07-20 10:00:00",
                        "type": "BUY",
                        "symbol": "AAPL",
                        "quantity": 10,
                        "price": 100,
                        "commission": 1,
                        "note": "momentum",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-07-21 12:00:00",
                        "type": "SELL",
                        "symbol": "AAPL",
                        "quantity": 10,
                        "price": 108,
                        "commission": 1,
                        "exit_reason": "take_profit",
                        "profit_loss": 80,
                    }
                ),
            ]
        )
        + "\n"
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["postmortem_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "up"
    assert glance["symbol"] == "AAPL"
    assert "Last exit · AAPL" in glance["line"]
    assert "take_profit" in glance["line"]
    assert "+8.0%" in glance["line"]


def test_chart_payload_book_risk_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    glance = payload["book_risk_glance"]
    assert glance["ready"] is True
    assert glance["posture"] == "open"
    assert glance["slots"] == "1/5"
    assert "1/5" in glance["line"]


def test_chart_payload_pretrade_glance(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    payload = load_chart_payload(tmp_path)
    glance = payload["pretrade_glance"]
    assert glance["ready"] is True
    assert glance["level"] == "PASS"
    assert glance["tone"] == "pass"


def test_chart_payload_soft_allow_glance(tmp_path: Path, monkeypatch):
    from stock_checker.gate_audit import record_soft_allow

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    record_soft_allow(tmp_path, "rs", "insufficient history")
    payload = load_chart_payload(tmp_path)
    glance = payload["soft_allow_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "warn"
    assert "[rs]" in glance["line"]
    assert "insufficient history" in glance["line"]


def test_chart_payload_scan_freshness_from_archive(tmp_path: Path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    scan_when = datetime.now(timezone.utc) - timedelta(minutes=5)
    stamp = scan_when.strftime("%Y-%m-%d %H:%M:%S")
    (tmp_path / "archive" / "opportunities_latest.json").write_text(
        json.dumps({"scan_time": stamp})
    )
    payload = load_chart_payload(tmp_path)
    fresh = payload["scan_freshness"]
    assert fresh["ready"] is True
    assert fresh["tone"] == "fresh"
    assert fresh["scan_time"] == stamp


def test_chart_payload_breadth_glance_from_daily(tmp_path: Path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    (tmp_path / "scan_breadth_daily.json").write_text(
        json.dumps(
            [
                {
                    "day": "2026-09-07",
                    "crypto_n": 4,
                    "crypto_up": 3,
                    "crypto_down": 1,
                    "crypto_big_movers": 1,
                    "stock_scan_n": 10,
                    "stock_scan_up": 6,
                    "stock_scan_down": 4,
                    "stock_within_5pct_high": 2,
                    "stock_breakouts_n": 3,
                }
            ]
        )
    )
    payload = load_chart_payload(tmp_path)
    glance = payload["breadth_glance"]
    assert glance["ready"] is True
    assert glance["tone"] == "up"
    assert "crypto 3/1" in glance["line"]
    assert "stock batch 6/4" in glance["line"]


def test_price_history_skips_nan(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import fetch_price_history

    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2026-07-01T00:00:00Z", "close": 100},
                    {"t": "2026-07-02T00:00:00Z", "close": float("nan")},
                    {"t": "2026-07-03T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    pts = fetch_price_history("AAPL", tmp_path, live=False)
    assert len(pts) == 2
    assert all(p["close"] == p["close"] for p in pts)  # no NaN


def test_unrealized_curve_offline(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import build_unrealized_curve

    _seed(tmp_path)
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"AAPL": 1721476800})  # 2024-07-20
    )
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2024-07-20T00:00:00Z", "close": 100},
                    {"t": "2024-07-21T00:00:00Z", "close": 105},
                    {"t": "2024-07-22T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    pts = build_unrealized_curve(tmp_path, live=False)
    assert len(pts) >= 2
    assert pts[-1]["unrealized"] == 100.0  # 10 * (110-100)
    assert abs(pts[-1]["unrealized_pct"] - 10.0) < 1e-6
    payload = load_chart_payload(tmp_path)
    assert "unrealized" in payload


def test_from_buy_panel_offline(tmp_path: Path, monkeypatch):
    from openbb_backend.charts import build_from_buy_panels

    _seed(tmp_path)
    (tmp_path / "entry_times.json").write_text(
        json.dumps({"AAPL": 1721476800})
    )
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    (cache / "AAPL.json").write_text(
        json.dumps(
            {
                "symbol": "AAPL",
                "fetched_at": 9e12,
                "points": [
                    {"t": "2024-07-19T00:00:00Z", "close": 90},
                    {"t": "2024-07-21T00:00:00Z", "close": 100},
                    {"t": "2024-07-22T00:00:00Z", "close": 110},
                ],
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    panels = build_from_buy_panels(tmp_path, live=False)
    assert panels
    aapl = next(p for p in panels if p["symbol"] == "AAPL")
    assert aapl["buy_price"] == 100
    assert aapl["points"][0]["rebased"] == 100
    assert aapl["change_pct"] == 10.0
    assert aapl["first_t"]
    assert aapl["last_t"]
    assert "span_hours" in aapl
    assert aapl["span_hours"] >= 0
    assert aapl["interval"] == "1d"


def test_hold_chart_interval_short_vs_long():
    from openbb_backend.charts import hold_chart_interval

    assert hold_chart_interval(7.0, is_crypto=True) == "15m"
    assert hold_chart_interval(48.0, is_crypto=True) == "1h"
    assert hold_chart_interval(200.0, is_crypto=False) == "1d"


def test_from_buy_short_crypto_uses_intraday_cache(tmp_path: Path, monkeypatch):
    """Short holds must not collapse to buy→now when only daily bars exist."""
    import time
    from datetime import datetime, timedelta, timezone

    from openbb_backend.charts import build_from_buy_panels

    buy_ts = time.time() - 7 * 3600
    (tmp_path / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 100000,
                "cash": 90000,
                "holdings": {"BTC-USD": 0.1},
                "avg_buy_price": {"BTC-USD": 64000},
                "total_fees_paid": 1,
            }
        )
    )
    (tmp_path / "trades.jsonl").write_text("")
    (tmp_path / "entry_times.json").write_text(json.dumps({"BTC-USD": buy_ts}))
    (tmp_path / "archive").mkdir(parents=True, exist_ok=True)
    (tmp_path / "archive" / "opportunities_latest.json").write_text("{}")
    cache = tmp_path / "chart_bars"
    cache.mkdir()
    t0 = datetime.fromtimestamp(buy_ts, tz=timezone.utc)
    pts = []
    for i in range(0, 8 * 4):
        ts = t0 + timedelta(minutes=15 * i)
        pts.append(
            {
                "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "close": 64000 + (i % 5) * 40 - 20,
            }
        )
    (cache / "BTC-USD_15m.json").write_text(
        json.dumps(
            {
                "symbol": "BTC-USD",
                "interval": "15m",
                "fetched_at": 9e12,
                "points": pts,
            }
        )
    )
    monkeypatch.setenv("DESK_CHART_LIVE", "0")
    panels = build_from_buy_panels(tmp_path, live=False)
    btc = next(p for p in panels if p["symbol"] == "BTC-USD")
    assert btc["interval"] == "15m"
    assert len(btc["points"]) > 5
