#!/usr/bin/env python3
"""Offline tests for OpenBB backend (no httpx required)."""

import json
from pathlib import Path

from openbb_backend import main as backend
from openbb_backend.desk import load_desk_snapshot


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
                "timestamp": "t",
                "type": "BUY",
                "symbol": "AAPL",
                "quantity": 10,
                "price": 100,
                "commission": 1,
            }
        )
        + "\n"
        + json.dumps(
            {
                "timestamp": "t2",
                "type": "SELL",
                "symbol": "AAPL",
                "quantity": 1,
                "price": 110,
                "commission": 1,
                "profit_loss": 9.0,
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
                    }
                ],
                "stock_breakouts": [
                    {
                        "symbol": "AAPL",
                        "sector": "tech",
                        "price": 105,
                        "pct_from_high": -0.02,
                        "strength": "STRONG",
                    }
                ],
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
    assert backend.root()["desk"] == "/desk"
    widgets = json.loads((Path(backend.__file__).parent / "widgets.json").read_text())
    assert "portfolio_markdown" in widgets


def test_desk_snapshot_rich(tmp_path: Path):
    _seed_portfolio(tmp_path)
    snap = load_desk_snapshot(
        tmp_path,
        live_marks=False,
        price_fetcher=lambda _syms: {},
    )
    assert snap["cash"] == 5000
    assert snap["positions"] == 2
    assert snap["realized"] == 9.0
    assert snap["buy_count"] == 1
    assert snap["sell_count"] == 1
    assert any(h["symbol"] == "BTC-USD" and h["kind"] == "crypto" for h in snap["holdings"])
    aapl = next(h for h in snap["holdings"] if h["symbol"] == "AAPL")
    assert aapl["marked"] is True
    assert aapl["last"] == 105
    assert aapl["unrealized"] > 0
    assert snap["recommendations"][0]["symbol"] == "ETH-USD"
    assert snap["crypto_leaders"][0]["symbol"] == "BTC-USD"
    assert snap["stock_breakouts"][0]["symbol"] == "AAPL"
    assert "needs_agent=0" in snap["watchdog"]
    assert snap["mark_source"] in {"scan", "live+scan"}


def test_desk_html_and_api(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.setenv("DESK_LIVE_MARKS", "0")
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    resp = client.get("/desk")
    assert resp.status_code == 200
    assert "AI Stock Checker" in resp.text
    assert "AAPL" in resp.text
    assert "Latest recommendations" in resp.text
    assert "ETH-USD" in resp.text
    api = client.get("/desk/api")
    assert api.status_code == 200
    body = api.json()
    assert body["positions"] == 2
    assert body["recommendations"][0]["reasoning"] == "test reason"
    css = client.get("/desk/static/desk.css")
    assert css.status_code == 200
    assert "Fraunces" in css.text
