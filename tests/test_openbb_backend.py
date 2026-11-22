#!/usr/bin/env python3
"""Offline tests for OpenBB backend (no httpx required)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import math

from openbb_backend import main as backend
from openbb_backend.desk import (
    _coerce_desk_mark,
    _coerce_desk_score,
    _coerce_desk_signed_pct,
    _prices_from_scan,
    load_desk_snapshot,
)


def _seed_portfolio(data: Path) -> None:
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": 10000,
                "cash": 5000,
                "holdings": {"AAPL": 10, "BTC-USD": 0.01},
                "avg_buy_price": {"AAPL": 100, "BTC-USD": 50000},
                "total_fees_paid": 12.5,
                "commission_rate": 0.001,
                "last_updated": "2026-07-25T00:00:00",
                "reset_note": "test reset",
            }
        )
    )
    (data / "trades.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-07-26 10:11:35",
                "type": "BUY",
                "symbol": "AAPL",
                "quantity": 10,
                "price": 100,
                "commission": 1,
                "strategy": "breakout",
                "note": "strong breakout, -1.20% from 52w high",
                "score": 38.8,
                "source": "scan",
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-07-28 12:00:00",
                "type": "SELL",
                "symbol": "AAPL",
                "quantity": 1,
                "price": 110,
                "commission": 1,
                "profit_loss": 9.0,
                "profit_loss_pct": 10.0,
                "exit_reason": "tp",
                "note": "Profit target +10.0% (thr +5%)",
            }
        )
        + "\n"
    )
    (data / "entry_times.json").write_text(
        json.dumps({"AAPL": 1700000000.0, "BTC-USD": 1700000000.0})
    )
    arch = data / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-07-26T10:00:00",
                "recommendations": [
                    {
                        "rank": 1,
                        "symbol": "ETH-USD",
                        "asset_class": "crypto",
                        "strategy": "momentum",
                        "score": 33.5,
                        "reasoning": "test reason",
                    }
                ],
                "crypto_leaders": [
                    {
                        "symbol": "BTC-USD",
                        "price": 60000,
                        "change_24h": 2.5,
                        "score": 70,
                        "volume_surge_pct": 10,
                        "tradeable": True,
                    },
                    {
                        "symbol": "ETH-USD",
                        "price": 3000,
                        "change_24h": -5.0,
                        "score": 40,
                        "volume_surge_pct": 5,
                        "tradeable": True,
                    },
                    {
                        "symbol": "SOL-USD",
                        "price": 150,
                        "change_24h": 0.0,
                        "score": 20,
                        "volume_surge_pct": 1,
                        "tradeable": True,
                    },
                ],
                "stock_breakouts": [
                    {
                        "symbol": "AAPL",
                        "sector": "tech",
                        "price": 105,
                        "pct_from_high": 1.5,
                        "strength": "STRONG",
                        "risk_note": "stop atr €100.00 (−4.8%) · tgt +20% · R:R 4.2 (ok)",
                        "risk_rr": 4.2,
                        "risk_rr_ok": True,
                    },
                    {
                        "symbol": "MSFT",
                        "sector": "tech",
                        "price": 400,
                        "pct_from_high": 12.0,
                        "strength": "WEAK",
                    },
                ],
                "stock_scan_pulse": {
                    "stock_scan_n": 30,
                    "stock_scan_up": 18,
                    "stock_scan_down": 10,
                    "stock_scan_flat": 2,
                    "stock_scan_batch": 30,
                },
            }
        )
    )
    (data / "scanned_symbols.json").write_text(
        json.dumps({"AAPL": {"source": "stock"}, "BTC-USD": {"source": "crypto"}})
    )
    (data / "stock_scan_history.json").write_text(
        json.dumps({"scanned": {"AAPL": "t"}, "last_full_cycle": "2026-07-26T09:00:00"})
    )
    wd = data / "watchdog"
    wd.mkdir(parents=True, exist_ok=True)
    (wd / "status.txt").write_text("needs_agent=0\nreasons=none\n")


def test_portfolio_endpoints_direct(tmp_path: Path, monkeypatch):
    data = tmp_path
    _seed_portfolio(data)
    monkeypatch.setattr(backend, "DATA_DIR", data)
    monkeypatch.setattr(backend, "API_KEY", "")

    rows = backend.portfolio_table()
    assert rows[0]["symbol"] in {"AAPL", "BTC-USD"}
    md = backend.portfolio_markdown().body.decode()
    assert "Paper Portfolio" in md
    trades = backend.trades_table(limit=10)
    assert trades[0]["symbol"] == "AAPL"
    assert backend.health()["ok"] is True
    home = backend.root()
    assert home.status_code == 302
    assert home.headers["location"] == "/desk"
    widgets = json.loads((Path(backend.__file__).parent / "widgets.json").read_text())
    assert "portfolio_markdown" in widgets


def test_portfolio_widgets_refuse_invalid_invents(tmp_path: Path, monkeypatch):
    """tradermonty #700/#655: OpenBB widgets must not invent €1 from bool marks."""
    data = tmp_path
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": True,
                "cash": True,
                "holdings": {"GOOD": 2, "BAD": True, "ZERO": 0},
                "avg_buy_price": {"GOOD": 50, "BAD": 10, "ZERO": 10, "GHOST": True},
                "total_fees_paid": True,
                "last_updated": "2026-11-17T00:00:00",
            }
        )
    )
    (data / "trades.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-11-17 12:00:00",
                "type": "SELL",
                "symbol": "X",
                "quantity": 1,
                "price": 10,
                "commission": 1,
                "profit_loss": True,
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-11-17 13:00:00",
                "type": "SELL",
                "symbol": "Y",
                "quantity": 1,
                "price": 20,
                "commission": 1,
                "profit_loss": 5.5,
            }
        )
        + "\n"
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    monkeypatch.setattr(backend, "API_KEY", "")

    rows = backend.portfolio_table()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "GOOD"
    assert rows[0]["quantity"] == 2.0
    assert rows[0]["avg_buy_price"] == 50.0
    assert rows[0]["cost_basis"] == 100.0

    md = backend.portfolio_markdown().body.decode()
    assert "**Initial capital:** €0.00" in md
    assert "**Cash:** €0.00" in md
    assert "**Fees paid:** €0.00" in md
    assert "**Holdings (cost basis):** €100.00" in md
    assert "**Positions:** 1" in md
    assert "**Realized P&L (sells):** €5.50" in md
    assert "€1.00" not in md  # True must not invent €1 anywhere


def test_trades_table_refuses_invalid_invents(tmp_path: Path, monkeypatch):
    """tradermonty #700/#655: OpenBB trades widget must not invent qty/€1 fills."""
    data = tmp_path
    (data / "portfolio.json").write_text(json.dumps({"cash": 1000, "holdings": {}}))
    (data / "trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-11-17 10:00:00",
                        "type": "BUY",
                        "symbol": "GOOD",
                        "quantity": 2,
                        "price": 50,
                        "commission": 1.25,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-11-17 11:00:00",
                        "type": "BUY",
                        "symbol": "BOOLQ",
                        "quantity": True,
                        "price": 50,
                        "commission": 1,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-11-17 12:00:00",
                        "type": "SELL",
                        "symbol": "ZEROPX",
                        "quantity": 1,
                        "price": 0,
                        "commission": 1,
                        "profit_loss": 3,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-11-17 13:00:00",
                        "type": "SELL",
                        "symbol": "BOOLFEE",
                        "quantity": 1,
                        "price": 20,
                        "commission": True,
                        "profit_loss": True,
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-11-17 14:00:00",
                        "type": "SELL",
                        "symbol": "OKSELL",
                        "quantity": 1,
                        "price": 30,
                        "commission": 0,
                        "profit_loss": -2.5,
                    }
                ),
            ]
        )
        + "\n"
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    monkeypatch.setattr(backend, "API_KEY", "")

    rows = backend.trades_table(limit=20)
    by_sym = {r["symbol"]: r for r in rows}
    assert by_sym["GOOD"]["fill_ok"] is True
    assert by_sym["GOOD"]["quantity"] == 2.0
    assert by_sym["GOOD"]["price"] == 50.0
    assert by_sym["GOOD"]["commission"] == 1.25

    assert by_sym["BOOLQ"]["fill_ok"] is False
    assert by_sym["BOOLQ"]["quantity"] is None
    assert by_sym["BOOLQ"]["price"] == 50.0

    assert by_sym["ZEROPX"]["fill_ok"] is False
    assert by_sym["ZEROPX"]["price"] is None
    assert by_sym["ZEROPX"]["quantity"] == 1.0

    assert by_sym["BOOLFEE"]["fill_ok"] is False
    assert by_sym["BOOLFEE"]["commission"] is None
    assert by_sym["BOOLFEE"]["profit_loss"] is None

    assert by_sym["OKSELL"]["fill_ok"] is True
    assert by_sym["OKSELL"]["commission"] == 0.0
    assert by_sym["OKSELL"]["profit_loss"] == -2.5


def test_opportunities_markdown_refuses_invalid_score(tmp_path: Path, monkeypatch):
    """tradermonty #700/#655 + staskh n/a: OpenBB opp widget must not invent scores."""
    data = tmp_path
    arch = data / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-11-18T00:00:00",
                "recommendations": [
                    {
                        "symbol": "ETH-USD",
                        "asset_class": "crypto",
                        "score": 33.5,
                        "reasoning": "ok momentum",
                    },
                    {
                        "symbol": "BAD-USD",
                        "asset_class": "crypto",
                        "score": True,
                        "reasoning": "bool invent",
                    },
                    {
                        "symbol": "GAP",
                        "asset_class": "stock",
                        "score": None,
                        "reasoning": "missing",
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    monkeypatch.setattr(backend, "API_KEY", "")

    md = backend.opportunities_markdown().body.decode()
    assert "ETH-USD" in md
    assert "score=33.5" in md
    assert "score=n/a" in md
    assert "score=True" not in md
    assert "score=1" not in md  # True must not invent 1


def test_coerce_desk_mark_refuses_invalid():
    assert _coerce_desk_mark(105.0) == 105.0
    assert _coerce_desk_mark(True) is None
    assert _coerce_desk_mark(False) is None
    assert _coerce_desk_mark(0) is None
    assert _coerce_desk_mark(-1) is None
    assert _coerce_desk_mark(math.nan) is None
    assert _coerce_desk_mark(None) is None
    assert _coerce_desk_mark("12.5") is None


def test_coerce_desk_score_refuses_bool_allows_zero():
    """tradermonty #700/#655: score may be 0; bool/NaN must not invent 1.0."""
    assert _coerce_desk_score(0) == 0.0
    assert _coerce_desk_score(42.5) == 42.5
    assert _coerce_desk_score(True) is None
    assert _coerce_desk_score(False) is None
    assert _coerce_desk_score(math.nan) is None
    assert _coerce_desk_score(None) is None
    assert _coerce_desk_score("9") is None


def test_coerce_desk_signed_pct_refuses_invalid():
    """Opportunities archive % — never invent flat 0.0 / True→1.0."""
    assert _coerce_desk_signed_pct(-1.5) == -1.5
    assert _coerce_desk_signed_pct(0.0) == 0.0
    assert _coerce_desk_signed_pct(2.25) == 2.25
    assert _coerce_desk_signed_pct(True) is None
    assert _coerce_desk_signed_pct(False) is None
    assert _coerce_desk_signed_pct(math.nan) is None
    assert _coerce_desk_signed_pct(None) is None
    assert _coerce_desk_signed_pct("1.2") is None


def test_desk_opportunities_signed_pct_refuse_invalid(
    tmp_path: Path, monkeypatch
):
    """Missing/bool archive % stay None — pulse does not invent flat or near-high."""
    data = tmp_path
    _seed_portfolio(data)
    arch = data / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-11-17T06:00:00",
                "recommendations": [],
                "crypto_leaders": [
                    {
                        "symbol": "BTC-USD",
                        "price": 60000,
                        "change_24h": True,
                        "score": 70,
                    },
                    {
                        "symbol": "ETH-USD",
                        "price": 3000,
                        "change_24h": None,
                        "score": 40,
                    },
                    {
                        "symbol": "SOL-USD",
                        "price": 150,
                        "change_24h": 3.0,
                        "score": 20,
                    },
                ],
                "stock_breakouts": [
                    {
                        "symbol": "AAPL",
                        "sector": "tech",
                        "price": 105,
                        "pct_from_high": False,
                        "strength": "STRONG",
                    },
                    {
                        "symbol": "MSFT",
                        "sector": "tech",
                        "price": 400,
                        "pct_from_high": 1.5,
                        "strength": "STRONG",
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    snap = load_desk_snapshot(data)
    btc = next(c for c in snap["crypto_leaders"] if c["symbol"] == "BTC-USD")
    eth = next(c for c in snap["crypto_leaders"] if c["symbol"] == "ETH-USD")
    sol = next(c for c in snap["crypto_leaders"] if c["symbol"] == "SOL-USD")
    assert btc["change_24h"] is None
    assert eth["change_24h"] is None
    assert sol["change_24h"] == 3.0
    aapl = next(s for s in snap["stock_breakouts"] if s["symbol"] == "AAPL")
    msft = next(s for s in snap["stock_breakouts"] if s["symbol"] == "MSFT")
    assert aapl["pct_from_high"] is None
    assert msft["pct_from_high"] == 1.5
    sb = snap["scan_breadth"]
    assert sb["crypto_n"] == 3
    assert sb["crypto_up"] == 1
    assert sb["crypto_down"] == 0
    assert sb["crypto_flat"] == 0  # unavailable ≠ invent flat
    assert abs(sb["crypto_avg_chg"] - 3.0) < 1e-9
    assert sb["stock_within_5pct_high"] == 1  # MSFT only; bool AAPL refused


def test_desk_breadth_crypto_avg_refuses_empty_or_bool(
    tmp_path: Path, monkeypatch
):
    """No readable 24h % → crypto_avg_chg None (never invent flat 0.0 / True→1)."""
    data = tmp_path
    _seed_portfolio(data)
    arch = data / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-11-18T01:00:00",
                "recommendations": [],
                "crypto_leaders": [
                    {
                        "symbol": "BTC-USD",
                        "price": 60000,
                        "change_24h": True,
                        "score": 70,
                    },
                    {
                        "symbol": "ETH-USD",
                        "price": 3000,
                        "change_24h": None,
                        "score": 40,
                    },
                ],
                "stock_breakouts": [],
            }
        )
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    snap = load_desk_snapshot(data)
    sb = snap["scan_breadth"]
    assert sb["crypto_n"] == 2
    assert sb["crypto_up"] == 0
    assert sb["crypto_down"] == 0
    assert sb["crypto_flat"] == 0
    assert sb["crypto_avg_chg"] is None
    hist = snap["scan_breadth_history"]
    assert hist
    assert hist[-1]["crypto_avg_chg"] is None
    daily = json.loads((data / "scan_breadth_daily.json").read_text())
    assert daily[-1]["crypto_avg_chg"] is None


def test_desk_breadth_stock_pulse_refuses_bool_counts(
    tmp_path: Path, monkeypatch
):
    """tradermonty #700/#655 + xang1234: True→1 must not invent stock A/D pulse."""
    data = tmp_path
    _seed_portfolio(data)
    arch = data / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-11-19T09:00:00",
                "recommendations": [],
                "crypto_leaders": [],
                "stock_breakouts": [],
                "stock_scan_pulse": {
                    "stock_scan_n": True,
                    "stock_scan_up": True,
                    "stock_scan_down": False,
                    "stock_scan_flat": True,
                },
            }
        )
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    snap = load_desk_snapshot(data)
    sb = snap["scan_breadth"]
    assert sb["stock_scan_n"] == 0
    assert sb["stock_scan_up"] == 0
    assert sb["stock_scan_down"] == 0
    assert sb["stock_scan_flat"] == 0
    assert sb["stock_advance_pct"] is None
    daily = json.loads((data / "scan_breadth_daily.json").read_text())
    assert daily[-1]["stock_scan_n"] == 0
    assert daily[-1]["stock_scan_up"] == 0
    assert daily[-1]["stock_scan_down"] == 0


def test_desk_snapshot_refuses_invalid_holdings_cash(tmp_path: Path, monkeypatch):
    """Bool/gap qty·avg·cash must not invent €1 Overview lots or book cash."""
    data = tmp_path
    _seed_portfolio(data)
    (data / "portfolio.json").write_text(
        json.dumps(
            {
                "initial_cash": True,  # invent €1 start if floated
                "cash": False,
                "holdings": {
                    "AAPL": 10,
                    "BADQTY": True,
                    "BADPX": 5,
                    "ZERO": 0,
                },
                "avg_buy_price": {
                    "AAPL": 100,
                    "BADQTY": 50,
                    "BADPX": True,
                    "ZERO": 10,
                },
                "total_fees_paid": True,
            }
        )
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    snap = load_desk_snapshot(data, live_marks=False, price_fetcher=lambda _s: {})
    symbols = {h["symbol"] for h in snap["holdings"]}
    assert symbols == {"AAPL"}
    assert snap["cash"] == 0.0
    assert snap["initial"] == 0.0
    assert snap["fees"] == 0.0
    aapl = snap["holdings"][0]
    assert aapl["quantity"] == 10.0
    assert aapl["avg_buy"] == 100.0
    assert aapl["cost_basis"] == 1000.0


def test_desk_snapshot_refuses_invalid_opportunity_price_score(
    tmp_path: Path, monkeypatch
):
    """Bool/gap price·score must not invent €1 / score 0 on Screener rows."""
    data = tmp_path
    _seed_portfolio(data)
    arch = data / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "opportunities_latest.json").write_text(
        json.dumps(
            {
                "scan_time": "2026-11-17T18:00:00",
                "recommendations": [
                    {
                        "rank": 1,
                        "symbol": "ETH-USD",
                        "asset_class": "crypto",
                        "strategy": "momentum",
                        "score": True,
                        "reasoning": "test",
                    },
                    {
                        "rank": 2,
                        "symbol": "AAPL",
                        "asset_class": "stock",
                        "strategy": "breakout",
                        "score": 38.8,
                        "reasoning": "ok",
                    },
                ],
                "crypto_leaders": [
                    {
                        "symbol": "BTC-USD",
                        "price": True,
                        "change_24h": 1.0,
                        "score": False,
                        "volume_surge_pct": True,
                    },
                    {
                        "symbol": "ETH-USD",
                        "price": 3000,
                        "change_24h": 2.0,
                        "score": 40,
                        "volume_surge_pct": 12.5,
                    },
                ],
                "stock_breakouts": [
                    {
                        "symbol": "AAPL",
                        "sector": "tech",
                        "price": 0,
                        "pct_from_high": 1.0,
                        "strength": "STRONG",
                    },
                    {
                        "symbol": "MSFT",
                        "sector": "tech",
                        "price": 400,
                        "pct_from_high": 1.5,
                        "strength": "STRONG",
                    },
                ],
            }
        )
    )
    monkeypatch.setattr(backend, "DATA_DIR", data)
    snap = load_desk_snapshot(data, live_marks=False, price_fetcher=lambda _s: {})
    eth_rec = next(r for r in snap["recommendations"] if r["symbol"] == "ETH-USD")
    aapl_rec = next(r for r in snap["recommendations"] if r["symbol"] == "AAPL")
    assert eth_rec["score"] is None
    assert aapl_rec["score"] == 38.8
    btc = next(c for c in snap["crypto_leaders"] if c["symbol"] == "BTC-USD")
    eth = next(c for c in snap["crypto_leaders"] if c["symbol"] == "ETH-USD")
    assert btc["price"] is None
    assert btc["score"] is None
    assert btc["volume_surge_pct"] is None
    assert eth["price"] == 3000.0
    assert eth["score"] == 40.0
    assert eth["volume_surge_pct"] == 12.5
    aapl = next(s for s in snap["stock_breakouts"] if s["symbol"] == "AAPL")
    msft = next(s for s in snap["stock_breakouts"] if s["symbol"] == "MSFT")
    assert aapl["price"] is None
    assert msft["price"] == 400.0
    # Book scan Score map reuses `_coerce_desk_score` (bool ETH rec / BTC False
    # cannot invent True→1.0); strip stays on book_risk, not snapshot top-level.


def test_prices_from_scan_skips_bool_and_nan():
    prices = _prices_from_scan(
        {
            "stock_breakouts": [
                {"symbol": "AAPL", "price": True},
                {"symbol": "MSFT", "price": math.nan},
                {"symbol": "IBM", "price": 190.5},
            ],
            "crypto_leaders": [
                {"symbol": "BTC-USD", "price": False},
                {"symbol": "ETH-USD", "price": 3000.0},
            ],
        }
    )
    assert prices == {"IBM": 190.5, "ETH-USD": 3000.0}


def test_desk_snapshot_invalid_scan_mark_falls_to_cost(tmp_path: Path):
    """Bool scan price must not mark the book at $1 (True→1.0)."""
    _seed_portfolio(tmp_path)
    arch = tmp_path / "archive" / "opportunities_latest.json"
    doc = json.loads(arch.read_text())
    for row in doc["stock_breakouts"]:
        if row.get("symbol") == "AAPL":
            row["price"] = True
    arch.write_text(json.dumps(doc))
    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
    )
    aapl = next(h for h in snap["holdings"] if h["symbol"] == "AAPL")
    assert aapl["marked"] is False
    assert aapl["last"] == 100


def test_desk_snapshot_realized_refuses_bool_pnl(tmp_path: Path):
    """Overview realized must not invent True→€1 / flat or 0 into sell P&L sum."""
    _seed_portfolio(tmp_path)
    trades = (tmp_path / "trades.jsonl").read_text(encoding="utf-8").rstrip() + "\n"
    trades += (
        json.dumps(
            {
                "timestamp": "2026-07-29 12:00:00",
                "type": "SELL",
                "symbol": "BOOL",
                "quantity": 1,
                "price": 10,
                "commission": 1,
                "profit_loss": True,
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "2026-07-29 13:00:00",
                "type": "SELL",
                "symbol": "OK",
                "quantity": 1,
                "price": 20,
                "commission": 1,
                "profit_loss": 2.5,
            }
        )
        + "\n"
    )
    (tmp_path / "trades.jsonl").write_text(trades, encoding="utf-8")
    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
    )
    # Seed sell +9 + OK +2.5; bool True must not add +1.
    assert snap["realized"] == 11.5
    assert snap["sell_count"] == 3


def test_desk_snapshot_rich(tmp_path: Path):
    _seed_portfolio(tmp_path)
    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
    )
    assert snap["cash"] == 5000
    assert snap["positions"] == 2
    assert snap["book_start"] == "2026-07-26"
    assert snap["book_age_days"] is not None
    assert snap["book_age_label"].startswith("2026-07-26 (")
    assert snap["realized"] == 9.0
    assert snap["buy_count"] == 1
    assert snap["sell_count"] == 1
    assert any(h["symbol"] == "BTC-USD" and h["kind"] == "crypto" for h in snap["holdings"])
    aapl = next(h for h in snap["holdings"] if h["symbol"] == "AAPL")
    assert aapl["marked"] is True
    assert aapl["last"] == 105
    assert aapl["unrealized"] > 0
    assert "unrealized_pct" in snap
    assert snap["unrealized_total"] == snap["market_value"] - snap["cost_basis_total"]
    if snap["cost_basis_total"]:
        expected = snap["unrealized_total"] / snap["cost_basis_total"] * 100
        assert abs(snap["unrealized_pct"] - expected) < 1e-6
    assert snap["recommendations"][0]["symbol"] == "ETH-USD"
    assert snap["pretrade_level"] in {"PASS", "WARN", "FAIL"}
    assert isinstance(snap["pretrade_notes"], list)
    assert isinstance(snap["soft_allows"], list)
    assert "ready" in snap["soft_allow_glance"]
    assert snap["soft_allow_glance"]["ready"] is False
    assert "ready" in snap["book_risk_glance"]
    assert snap["book_risk_glance"]["ready"] is True
    assert snap["book_risk_glance"]["posture"] in {"open", "at_cap", "overweight"}
    assert "eur" in snap["entry_size"]
    assert snap["entry_size"]["slots_open"] >= 0
    assert "ready" in snap["next_buy_glance"]
    assert snap["next_buy_glance"]["ready"] is True
    assert snap["crypto_leaders"][0]["symbol"] == "BTC-USD"
    assert len(snap["crypto_leaders"]) == 3  # top list capped for UI; pulse uses full scan
    assert "tone" in snap["scan_freshness"]
    assert snap["scan_freshness"]["ready"] is True
    assert snap["scan_freshness"]["tone"] in {"fresh", "aging", "stale", "unknown"}
    assert snap["stock_breakouts"][0]["symbol"] == "AAPL"
    assert snap["stock_breakouts"][0]["name"] == "Apple"
    sb = snap["scan_breadth"]
    assert sb["crypto_n"] == 3
    assert sb["crypto_up"] == 1
    assert sb["crypto_down"] == 1
    assert sb["crypto_flat"] == 1
    assert sb["crypto_big_movers"] == 1  # ETH −5%
    assert abs(sb["crypto_avg_chg"] - ((2.5 - 5.0 + 0.0) / 3)) < 1e-9
    assert sb["stock_breakouts_n"] == 2
    assert sb["stock_within_5pct_high"] == 1
    assert sb["stock_scan_n"] == 30
    assert sb["stock_scan_up"] == 18
    assert sb["stock_scan_down"] == 10
    assert snap["stock_breakouts"][0]["risk_note"]
    assert snap["scan_breadth_history"]
    assert snap["scan_breadth_history"][-1]["crypto_up"] == 1
    assert (tmp_path / "scan_breadth_daily.json").exists()
    assert any(h["symbol"] == "BTC-USD" and h["name"] == "Bitcoin" for h in snap["holdings"])
    assert "needs_agent=0" in snap["watchdog"]
    assert snap["mark_source"] in {"scan", "live+scan"}
    assert snap["mark_coverage"]["severity"] == "ok"
    assert snap["mark_coverage"]["bit"] == "price coverage ok · 2/2"
    assert "price coverage ok · 2/2" in snap["mark_note"]
    assert snap["ledger_health"]["severity"] == "ok"
    assert snap["ledger_health"]["line"] == "ledger ok"
    assert snap["github_ideas"] == []
    assert snap["github_watch_updates"] == 0
    assert snap["github_watch_has_digest"] is False
    assert snap["adopted_ideas"]
    assert snap["github_repos"] == []
    assert snap["github_watch_notes"] == []
    assert "ai_mode" in snap["runtime"]
    assert snap["runtime"]["max_positions"] == 5
    assert snap["runtime"]["promote_experiment_strategy"] is False
    assert "trader_version" in snap["runtime"]
    assert snap["runtime"]["python_expected"] == "3.11"
    assert "python_running" in snap["runtime"]
    assert "python_pin_ok" in snap["runtime"]
    assert "llm_key_set" in snap["runtime"]
    assert "regime_gate" in snap["runtime"]
    assert "rs_gate" in snap["runtime"]
    assert "breadth_gate" in snap["runtime"]
    assert "calm_streak_days" in snap["runtime"]
    assert "calm_hint" in snap["runtime"]
    assert "stock_regime" in snap["runtime"]
    assert "stock_regime_label" in snap["runtime"]
    assert "crypto_regime_label" in snap["runtime"]
    assert "config_source" in snap["runtime"]
    # Never leak secrets into the desk snapshot
    assert "OPENAI_API_KEY" not in str(snap["runtime"])
    assert "api_key" not in str(snap["runtime"]).lower()


def test_github_watch_notes_include_last_commit_date(tmp_path: Path):
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-26T10:27:37Z",
                "repo_count": 2,
                "checked_count": 2,
                "update_count": 0,
                "idea_bullets": [],
                "repos": [
                    {
                        "repo": "acme/old",
                        "url": "https://github.com/acme/old",
                        "why": "older tip",
                        "stars": 1,
                        "pushed_at": "2026-06-01T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": "1111111111111111",
                        "tip_message": "Old idea",
                        "commits": [
                            {
                                "sha": "1111111111111111deadbeef",
                                "date": "2026-06-01T08:00:00Z",
                                "message": "Old idea",
                            }
                        ],
                    },
                    {
                        "repo": "acme/screener",
                        "url": "https://github.com/acme/screener",
                        "why": "test",
                        "stars": 3,
                        "pushed_at": "2026-07-20T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": "abcdef0123456789",
                        "tip_message": "Tune breadth window",
                        "commits": [
                            {
                                "sha": "abcdef0123456789deadbeef",
                                "date": "2026-07-19T08:15:00Z",
                                "message": "Tune breadth window",
                            }
                        ],
                    },
                ],
            }
        )
    )
    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
    )
    assert snap["github_watch_has_digest"] is True
    # Newest last_commit_at first (Quiet tips + repo list).
    assert snap["github_repos"][0]["repo"] == "acme/screener"
    assert snap["github_repos"][0]["last_commit_at"] == "2026-07-19"
    assert snap["github_repos"][1]["repo"] == "acme/old"
    assert "acme/screener: latest abcdef0 · 2026-07-19" in snap["github_watch_notes"][0]
    assert "acme/old:" in snap["github_watch_notes"][1]


def test_github_watch_digest_refuses_bool_counts(tmp_path: Path):
    """int(True)→1 must not invent Ideas «1 with new activity» / 1★."""
    _seed_portfolio(tmp_path)
    gw = tmp_path / "github_watch"
    gw.mkdir(parents=True, exist_ok=True)
    (gw / "latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-11-22T20:56:09Z",
                "repo_count": True,
                "checked_count": False,
                "update_count": True,
                "idea_bullets": [],
                "repos": [
                    {
                        "repo": "acme/quiet",
                        "url": "https://github.com/acme/quiet",
                        "why": "test",
                        "stars": True,
                        "pushed_at": "2026-11-20T12:00:00Z",
                        "has_updates": False,
                        "tip_sha": "",
                        "tip_message": "",
                        "commits": [],
                    }
                ],
            }
        )
    )
    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
    )
    assert snap["github_watch_updates"] == 0
    assert snap["github_watch_repos"] == 0
    assert snap["github_watch_checked"] == 0
    assert snap["github_repos"][0]["stars"] == 0


def test_desk_config_api_put(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    bad = client.put("/desk/api/config", json={"ai_mode": "nope"})
    assert bad.status_code == 400
    secret = client.put("/desk/api/config", json={"api_key": "x", "ai_mode": "validate"})
    assert secret.status_code == 400
    ok = client.put(
        "/desk/api/config",
        json={
            "ai_mode": "validate",
            "ai_model": "gemma4:latest",
            "ai_multi_role": True,
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "fee_preset": "revolut_standard",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["ai_mode"] == "validate"
    assert ok.json()["fee_preset"] == "revolut_standard"
    assert ok.json().get("rs_gate") is True
    assert ok.json().get("breadth_gate") is True
    assert abs(ok.json()["commission_rate"] - 0.0025) < 1e-9
    assert ok.json().get("audit_outcome") == "accepted"
    assert ok.json().get("action_id")
    # xang1234 #636: Save response + glance speak which knobs moved.
    assert isinstance(ok.json().get("changed"), list)
    assert ok.json().get("changed")
    assert str(ok.json().get("changed_bit") or "").startswith("Δ ")
    assert (tmp_path / "trader_config.json").exists()
    assert (tmp_path / "ops_actions.json").exists()
    got = client.get("/desk/api/config")
    assert got.status_code == 200
    assert got.json()["ai_mode"] == "validate"
    last_ops = str(got.json().get("last_ops_action") or "")
    assert "last config · accepted" in last_ops
    assert "Δ " in last_ops


def test_desk_config_api_put_refuses_pending_in_flight(tmp_path: Path, monkeypatch):
    """Fresh hanging requested → 409; does not rewrite trader_config."""
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from stock_checker.ops_audit import append_ops_action
    from stock_checker.trader_config import save_trader_config
    from starlette.testclient import TestClient

    save_trader_config(tmp_path, {"ai_mode": "off"})
    append_ops_action(
        tmp_path,
        {
            "id": "hang",
            "action_id": "act-hang",
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "config",
            "outcome": "requested",
            "detail": {},
        },
    )
    client = TestClient(backend.app)
    refused = client.put(
        "/desk/api/config",
        json={"ai_mode": "validate", "fee_preset": "revolut_standard"},
    )
    assert refused.status_code == 409
    detail = str(refused.json().get("detail") or "")
    assert "in flight" in detail.lower()
    # Prior saved row must remain (no silent overwrite).
    from stock_checker.trader_config import load_trader_config

    assert load_trader_config(tmp_path).get("ai_mode") == "off"


def test_desk_config_api_dry_run_preview_no_write(tmp_path: Path, monkeypatch):
    """xang1234 #636 confirm-first: dry_run returns impact without audit/write."""
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from stock_checker.ops_audit import load_ops_actions
    from stock_checker.trader_config import load_trader_config, save_trader_config
    from starlette.testclient import TestClient

    save_trader_config(
        tmp_path,
        {
            "ai_mode": "off",
            "fee_preset": "revolut_standard",
            "min_hold_hours": 24,
            "max_positions": 5,
        },
    )
    mtime_before = (tmp_path / "trader_config.json").stat().st_mtime_ns
    client = TestClient(backend.app)
    hot = client.put(
        "/desk/api/config?dry_run=1",
        json={
            "ai_mode": "off",
            "fee_preset": "revolut_standard",
            "min_hold_hours": 48,
            "max_positions": 5,
        },
    )
    assert hot.status_code == 200
    body = hot.json()
    assert body.get("dry_run") is True
    assert body.get("needs_confirm") is True
    assert body.get("changed_impact_severity") == "hot"
    assert "min_hold_hours" in (body.get("changed") or [])
    assert str(body.get("changed_bit") or "").startswith("Δ hot")
    assert "Continue?" in str(body.get("confirm") or "")
    # Mid-session fields always present on hot dry-run (may be empty off-hours).
    assert "open_cash" in body
    assert "session_bit" in body
    assert "mid_session" in body
    assert isinstance(body.get("open_cash"), list)
    if body.get("mid_session"):
        assert "mid session" in str(body.get("confirm") or "")
        assert body.get("session_bit")
    quiet = client.put(
        "/desk/api/config?dry_run=1",
        json={
            "ai_mode": "validate",
            "fee_preset": "revolut_standard",
            "min_hold_hours": 24,
            "max_positions": 5,
        },
    )
    assert quiet.status_code == 200
    q = quiet.json()
    assert q.get("needs_confirm") is False
    assert q.get("changed_impact_severity") == "quiet"
    assert q.get("confirm") == ""
    noop = client.put(
        "/desk/api/config?dry_run=1",
        json={
            "ai_mode": "off",
            "fee_preset": "revolut_standard",
            "min_hold_hours": 24,
            "max_positions": 5,
        },
    )
    assert noop.status_code == 200
    assert noop.json().get("changed") == []
    assert noop.json().get("needs_confirm") is False
    # Dry-run must not rewrite disk or append audit rows.
    assert (tmp_path / "trader_config.json").stat().st_mtime_ns == mtime_before
    assert load_trader_config(tmp_path).get("ai_mode") == "off"
    assert load_trader_config(tmp_path).get("min_hold_hours") == 24
    assert load_ops_actions(tmp_path) == []


def test_desk_config_api_put_refuses_noop(tmp_path: Path, monkeypatch):
    """xang1234 #623: equal knobs → 409 skipped; no trader_config rewrite."""
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from stock_checker.ops_audit import last_ops_action, load_ops_actions
    from stock_checker.trader_config import load_trader_config, save_trader_config
    from starlette.testclient import TestClient

    saved = save_trader_config(
        tmp_path,
        {
            "ai_mode": "validate",
            "ai_model": "gemma4:latest",
            "ai_multi_role": True,
            "regime_gate": True,
            "rs_gate": True,
            "breadth_gate": True,
            "fee_preset": "revolut_standard",
        },
    )
    mtime_before = (tmp_path / "trader_config.json").stat().st_mtime_ns
    client = TestClient(backend.app)
    refused = client.put(
        "/desk/api/config",
        json={
            "ai_mode": saved["ai_mode"],
            "ai_model": saved["ai_model"],
            "ai_multi_role": saved["ai_multi_role"],
            "regime_gate": saved["regime_gate"],
            "rs_gate": saved["rs_gate"],
            "breadth_gate": saved["breadth_gate"],
            "fee_preset": saved["fee_preset"],
        },
    )
    assert refused.status_code == 409
    assert "skipped" in str(refused.json().get("detail") or "").lower()
    assert (tmp_path / "trader_config.json").stat().st_mtime_ns == mtime_before
    assert load_trader_config(tmp_path).get("ai_mode") == "validate"
    last = last_ops_action(tmp_path, kind="config")
    assert last is not None
    assert last["outcome"] == "skipped"
    assert last.get("reason") == "no-op"
    # No requested/accepted pair for a refused no-op.
    assert [e["outcome"] for e in load_ops_actions(tmp_path)] == ["skipped"]
    from stock_checker.ops_audit import format_last_ops_action_bit

    assert "skipped · no-op" in format_last_ops_action_bit(last)


def test_desk_ops_has_config_form(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
    from stock_checker.gate_audit import record_soft_allow

    record_soft_allow(tmp_path, "promote", "XYZ: skip_no_bars")
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    resp = client.get("/desk/ops")
    assert resp.status_code == 200
    assert 'data-ops-config' in resp.text
    assert 'id="ops-ai-mode"' in resp.text
    assert 'data-ops-logs' in resp.text
    assert 'id="ops-log-view"' in resp.text
    assert "Fail-open soft-allows" in resp.text
    assert "skip_no_bars" in resp.text
    assert "[promote]" in resp.text
    assert "breadth-glance" in resp.text
    assert "ops-breadth-h" in resp.text
    assert "breadth gate" in resp.text
    assert "ops-pretrade-h" in resp.text
    assert "pretrade-level" in resp.text
    assert "Buy-halt honesty before knobs" in resp.text
    assert "soft-allow-glance" in resp.text
    assert 'href="#soft-h"' in resp.text
    assert "Memory below" in resp.text
    assert "book-risk-glance" in resp.text
    assert "ops-book-risk-h" in resp.text
    assert "book limits" in resp.text
    assert "not a calibrated market-top probability" in resp.text


def test_desk_ops_soft_allow_lead_row_tag(tmp_path: Path, monkeypatch):
    """portfolio AI + xang1234: Ops list marks glance lead + runner gate×band."""
    _seed_portfolio(tmp_path)
    from stock_checker.gate_audit import record_soft_allow

    record_soft_allow(tmp_path, "rs", "insufficient a")
    record_soft_allow(tmp_path, "rs", "insufficient b")
    record_soft_allow(tmp_path, "regime", "unknown — no SPY bars")
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    resp = client.get("/desk/ops")
    assert resp.status_code == 200
    assert "soft-allow-lead" in resp.text
    assert "soft-allow-lead-tag" in resp.text
    # Band identity on the tag (not bare "leads") — ≠ row aging/expired.
    assert ">leads · fresh<" in resp.text
    assert "leads · band" in resp.text
    assert resp.text.count("soft-allow-lead-tag") == 2
    # Speak-both-sides: runner gate×band gets vs · band (not accent lead).
    assert "soft-allow-runner" in resp.text
    assert "soft-allow-runner-tag" in resp.text
    assert ">vs · fresh<" in resp.text
    assert "vs · band" in resp.text
    assert resp.text.count("soft-allow-runner-tag") == 1
    # Ops inventory: Lead owns concentration; Runner is its own speak-both-sides line.
    assert "soft-allow-lead-summary" in resp.text
    assert "Lead · rs ×2 · fresh · 67% · ahead thin · +1 · share Δ wide · +33pp" in resp.text
    assert "soft-allow-runner-summary" in resp.text
    assert "Runner · regime ×1 · fresh · 33% · behind thin · −1" in resp.text
    lead_summary = resp.text.split("soft-allow-lead-summary", 1)[1].split("</p>", 1)[0]
    assert "vs " not in lead_summary
    assert "behind " not in lead_summary
    assert "Lead · gate ×N · band · M%" in resp.text
    assert "ahead · +K" in resp.text
    assert "Runner · gate ×K · band · P%" in resp.text
    assert "behind · −K" in resp.text


def test_desk_ops_soft_allow_lead_inventory_sole(tmp_path: Path, monkeypatch):
    """Sole-gate lead inventory speaks 100% ownership; omits ahead/runner (no runner)."""
    _seed_portfolio(tmp_path)
    from stock_checker.gate_audit import record_soft_allow

    record_soft_allow(tmp_path, "rs", "insufficient a")
    record_soft_allow(tmp_path, "rs", "insufficient b")
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    resp = client.get("/desk/ops")
    assert resp.status_code == 200
    assert "soft-allow-lead-summary" in resp.text
    assert "Lead · rs ×2 · fresh · 100%" in resp.text
    summary = resp.text.split("soft-allow-lead-summary", 1)[1].split("</p>", 1)[0]
    assert "ahead " not in summary
    assert "vs " not in summary
    assert "share Δ" not in summary
    assert "soft-allow-runner-summary" not in resp.text
    lead_only = resp.text.split("soft-allow-lead-summary", 1)[1].split("</p>", 1)[0]
    assert "Runner ·" not in lead_only


def test_desk_breadth_day_meta_mismatch(tmp_path: Path, monkeypatch):
    """xang1234: Recent days + scan-log warn when scan_time misses the UTC day."""
    _seed_portfolio(tmp_path)
    # Use a past UTC day so today's upsert does not replace the fixture row.
    day = "2026-09-20"
    arch = tmp_path / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / f"opportunities_{day.replace('-', '')}_120000.txt").write_text(
        "TOP NAMES\nAAPL\n", encoding="utf-8"
    )
    (tmp_path / "scan_breadth_daily.json").write_text(
        json.dumps(
            [
                {
                    "day": day,
                    "scan_time": "2026-09-19T12:00:00Z",
                    "crypto_n": 2,
                    "crypto_up": 1,
                    "crypto_down": 1,
                    "crypto_avg_chg": 0.5,
                    "crypto_big_movers": 0,
                    "stock_breakouts_n": 1,
                    "stock_within_5pct_high": 0,
                    "stock_scan_n": 4,
                    "stock_scan_up": 2,
                    "stock_scan_down": 2,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    breadth = client.get("/desk/breadth")
    assert breadth.status_code == 200
    assert "meta mismatch · scan on 2026-09-19" in breadth.text
    assert "scan_time must cover the day" in breadth.text
    log_page = client.get(f"/desk/scan-log/{day}")
    assert log_page.status_code == 200
    assert "scan-log-day-meta-h" in log_page.text
    assert "meta mismatch · scan on 2026-09-19" in log_page.text


def test_desk_overview_soft_allow_glance(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
    from stock_checker.gate_audit import record_soft_allow

    record_soft_allow(tmp_path, "regime", "unknown — no SPY bars")
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    overview = client.get("/desk/")
    assert overview.status_code == 200
    assert "soft-allow-glance" in overview.text
    assert "no SPY bars" in overview.text
    assert "/desk/ops#soft-h" in overview.text
    book = client.get("/desk/book")
    assert book.status_code == 200
    assert "soft-allow-glance" in book.text
    assert "Ops memory" in book.text
    screener = client.get("/desk/screener")
    assert screener.status_code == 200
    assert "soft-allow-glance" in screener.text
    ideas = client.get("/desk/ideas")
    assert ideas.status_code == 200
    assert "soft-allow-glance" in ideas.text
    assert "no SPY bars" in ideas.text
    breadth = client.get("/desk/breadth")
    assert breadth.status_code == 200
    assert "soft-allow-glance" in breadth.text
    assert "Ops memory" in breadth.text
    assert "pretrade-glance" in breadth.text
    assert "breadth-pretrade-h" in breadth.text
    assert "Pre-trade" in breadth.text
    day = "2026-09-08"
    arch = tmp_path / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / f"opportunities_{day.replace('-', '')}_120000.txt").write_text(
        "TOP NAMES\nBTC-USD\n", encoding="utf-8"
    )
    log_page = client.get(f"/desk/scan-log/{day}")
    assert log_page.status_code == 200
    assert "soft-allow-glance" in log_page.text
    assert "no SPY bars" in log_page.text
    assert "pretrade-glance" in log_page.text
    assert "scan-log-pretrade-h" in log_page.text
    assert "book-risk-glance" in log_page.text
    assert "scan-log-book-risk-h" in log_page.text


def test_desk_html_screens(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    resp = client.get("/desk")
    assert resp.status_code == 200
    assert "Skip to content" in resp.text
    assert 'rel="icon"' in resp.text
    assert 'name="description"' in resp.text
    assert 'aria-current="page"' in resp.text
    assert "Desk screens" in resp.text
    assert "refresh-eta" in resp.text
    assert 'data-seconds="300"' in resp.text
    assert "fonts.googleapis" not in resp.text
    assert "GitHub" in resp.text
    assert resp.headers.get("content-security-policy", "").find("img-src 'self'") >= 0

    for path in ("/desk/charts", "/desk/screener", "/desk/breadth", "/desk/book", "/desk/ideas", "/desk/ops"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "AI Stock Checker" in r.text

    assert "Apple" in client.get("/desk/screener").text
    screener = client.get("/desk/screener")
    assert 'aria-label="Screener counts"' in screener.text
    assert "populated this scan" in screener.text
    assert ">Total<" in screener.text or "Total" in screener.text
    assert "row slots" in screener.text or "unique" in screener.text
    assert "breadth-glance" in screener.text
    assert "screener-breadth-h" in screener.text
    assert "Full breadth" in screener.text
    overview = client.get("/desk")
    assert "Bitcoin" in overview.text
    assert "breadth-glance" in overview.text
    assert "Full breadth" in overview.text
    assert "Scan-list estimate with priced counts" in overview.text
    breadth = client.get("/desk/breadth")
    assert "Scan pulse" in breadth.text
    assert "Crypto A/D" in breadth.text
    assert "Recent days" in breadth.text
    assert 'id="pulse-key"' in breadth.text
    assert "breadth-days-table" in breadth.text
    assert "near-high" in breadth.text
    assert "book-risk-glance" in breadth.text
    assert "breadth-book-risk-h" in breadth.text
    assert "Slots and posture beside breadth" in breadth.text

    # Seed a day archive so Breadth can link the scan log.
    day = "2026-07-26"
    arch = tmp_path / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / f"opportunities_{day.replace('-', '')}_120000.txt").write_text(
        "TOP NAMES\nBTC-USD\n", encoding="utf-8"
    )
    hist = tmp_path / "scan_breadth_daily.json"
    hist.write_text(
        json.dumps(
            [
                {
                    "day": "2026-07-25",
                    "crypto_up": 0,
                    "crypto_down": 2,
                    "crypto_avg_chg": -1.0,
                    "crypto_big_movers": 1,
                    "stock_within_5pct_high": 0,
                },
                {
                    "day": day,
                    "crypto_up": 1,
                    "crypto_down": 0,
                    "crypto_avg_chg": 1.0,
                    "crypto_big_movers": 0,
                    "stock_within_5pct_high": 1,
                },
            ]
        ),
        encoding="utf-8",
    )
    breadth2 = client.get("/desk/breadth")
    assert f"/desk/scan-log/{day}" in breadth2.text
    assert 'id="breadth-ad-spark"' in breadth2.text
    assert "Crypto A/D net" in breadth2.text
    assert "breadth-ad-spark-svg" in breadth2.text
    assert "stock A/D" in breadth2.text
    # Seed stock batch A/D history → second spark appears after ≥2 days.
    hist.write_text(
        json.dumps(
            [
                {
                    "day": "2026-07-25",
                    "crypto_up": 0,
                    "crypto_down": 2,
                    "crypto_avg_chg": -1.0,
                    "crypto_big_movers": 1,
                    "stock_within_5pct_high": 0,
                    "stock_scan_n": 10,
                    "stock_scan_up": 2,
                    "stock_scan_down": 6,
                },
                {
                    "day": day,
                    "crypto_up": 1,
                    "crypto_down": 0,
                    "crypto_avg_chg": 1.0,
                    "crypto_big_movers": 0,
                    "stock_within_5pct_high": 1,
                    "stock_scan_n": 12,
                    "stock_scan_up": 8,
                    "stock_scan_down": 3,
                },
            ]
        ),
        encoding="utf-8",
    )
    breadth3 = client.get("/desk/breadth")
    assert 'id="breadth-stock-ad-spark"' in breadth3.text
    assert "Stock batch A/D net" in breadth3.text
    assert "8/3" in breadth3.text
    log_page = client.get(f"/desk/scan-log/{day}")
    assert log_page.status_code == 200
    assert "BTC-USD" in log_page.text
    assert "breadth-glance" in log_page.text
    assert "scan-log-breadth-h" in log_page.text
    assert "crypto 1/0" in log_page.text
    assert "stock 8/3" in log_page.text
    assert "estimate · not full-universe" in log_page.text
    assert "scan-fresh" in log_page.text
    assert "pretrade-glance" in log_page.text
    assert "scan-log-pretrade-h" in log_page.text
    assert "book-risk-glance" in log_page.text
    assert "scan-log-book-risk-h" in log_page.text
    assert client.get("/desk/scan-log/1999-01-01").status_code == 404
    assert "Scan-log day breadth glance" in client.get("/desk/ideas").text
    book = client.get("/desk/book")
    assert "hold-spark" in book.text
    assert "average buy" in book.text.lower() or "avg cost" in book.text.lower()
    assert "+10.0%" in book.text
    assert "breakout" in book.text
    assert "52w high" in book.text
    assert "Profit target" in book.text
    assert "data/trades.jsonl" in book.text
    assert "breadth-glance" in book.text
    assert "book-breadth-h" in book.text
    assert "Full breadth" in book.text
    assert "context for adds" in book.text
    assert "scan-fresh" in book.text
    ideas = client.get("/desk/ideas")
    assert "Paper candidates" in ideas.text
    assert "Adopted here" in ideas.text
    assert "Book breadth beside holdings" in ideas.text
    assert "No GitHub watch digest yet" in ideas.text  # seeded fixture has no watch file
    assert "scan-fresh" in ideas.text
    assert "Book / Ideas / Charts" in ideas.text
    assert "d3.min.js" in client.get("/desk/charts").text
    assert "charts.js" in client.get("/desk/charts").text
    assert "hold-spark" in client.get("/desk/book").text
    assert "d3.min.js" in client.get("/desk/book").text
    assert "Buys / Sells" in client.get("/desk").text
    assert "unreal-spark" in client.get("/desk").text
    assert "ch-unreal" in client.get("/desk").text
    overview = client.get("/desk")
    assert "pretrade" in overview.text
    assert "Next buy" in overview.text or "No new buy size" in overview.text
    assert "Pre-trade + position sizer" in client.get("/desk/ideas").text

    ops = client.get("/desk/ops")
    assert ops.text.find("Trader config") >= 0
    assert "AI mode" in ops.text
    assert "Live logs" in ops.text
    assert "breadth-glance" in ops.text
    assert "ops-breadth-h" in ops.text
    assert "Ops breadth beside gate knobs" in client.get("/desk/ideas").text

    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "logs" / "trader.log").write_text("tee-line\n", encoding="utf-8")
    logs_list = client.get("/desk/api/logs")
    assert logs_list.status_code == 200
    assert logs_list.json()["default"] == "trader"
    tail = client.get("/desk/api/logs/trader")
    assert tail.status_code == 200
    assert "tee-line" in tail.json()["text"]
    assert client.get("/desk/api/logs/nope").status_code == 404

    charts = client.get("/desk/api/charts")
    assert charts.status_code == 200
    body = charts.json()
    assert "equity" in body and "allocation" in body
    assert "from_buy" in body
    assert "unrealized" in body
    assert "breadth_glance" in body
    assert "ready" in body["breadth_glance"]

    assert client.get("/desk/nope").status_code == 404
    api = client.get("/desk/api")
    assert api.status_code == 200
    assert api.json()["positions"] == 2

    ico = client.get("/desk/static/favicon.ico")
    assert ico.status_code == 200
    assert ico.content[:4] == b"\x00\x00\x01\x00" or ico.content[:4] == b"\x00\x00\x01\x00"
    svg = client.get("/desk/static/favicon.svg")
    assert svg.status_code == 200
    assert b"<svg" in svg.content
    root_ico = client.get("/favicon.ico")
    assert root_ico.status_code == 200
