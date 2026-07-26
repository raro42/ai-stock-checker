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


def test_desk_snapshot(tmp_path: Path):
    _seed_portfolio(tmp_path)
    snap = load_desk_snapshot(tmp_path)
    assert snap["cash"] == 5000
    assert snap["positions"] == 2
    assert snap["realized"] == 9.0
    assert any(h["symbol"] == "BTC-USD" and h["kind"] == "crypto" for h in snap["holdings"])
    assert snap["reset_note"] == "test reset"


def test_desk_html_renders(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    from starlette.testclient import TestClient

    client = TestClient(backend.app)
    resp = client.get("/desk")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "AI Stock Checker" in resp.text
    assert "AAPL" in resp.text
    css = client.get("/desk/static/desk.css")
    assert css.status_code == 200
    assert "Fraunces" in css.text
