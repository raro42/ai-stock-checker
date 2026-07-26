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
    assert "screener" in backend.root()["desk_screens"]
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
    assert "unrealized_pct" in snap
    assert snap["unrealized_total"] == snap["market_value"] - snap["cost_basis_total"]
    if snap["cost_basis_total"]:
        expected = snap["unrealized_total"] / snap["cost_basis_total"] * 100
        assert abs(snap["unrealized_pct"] - expected) < 1e-6
    assert snap["recommendations"][0]["symbol"] == "ETH-USD"
    assert snap["crypto_leaders"][0]["symbol"] == "BTC-USD"
    assert snap["stock_breakouts"][0]["symbol"] == "AAPL"
    assert snap["stock_breakouts"][0]["name"] == "Apple"
    assert any(h["symbol"] == "BTC-USD" and h["name"] == "Bitcoin" for h in snap["holdings"])
    assert "needs_agent=0" in snap["watchdog"]
    assert snap["mark_source"] in {"scan", "live+scan"}
    assert snap["github_ideas"] == []
    assert snap["github_watch_updates"] == 0


def test_desk_screens_seo_a11y_favicon(tmp_path: Path, monkeypatch):
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
    assert "Bitcoin" in client.get("/desk").text
    assert "d3.min.js" in client.get("/desk/charts").text
    assert "charts.js" in client.get("/desk/charts").text
    assert "hold-spark" in client.get("/desk/book").text
    assert "d3.min.js" in client.get("/desk/book").text
    assert "Buys / Sells" in client.get("/desk").text

    charts = client.get("/desk/api/charts")
    assert charts.status_code == 200
    body = charts.json()
    assert "equity" in body and "allocation" in body
    assert "from_buy" in body

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
