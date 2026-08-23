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
                "timestamp": "2026-07-26 10:11:35",
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
                "timestamp": "2026-07-28 12:00:00",
                "type": "SELL",
                "symbol": "AAPL",
                "quantity": 1,
                "price": 110,
                "commission": 1,
                "profit_loss": 9.0,
                "profit_loss_pct": 10.0,
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
    assert snap["crypto_leaders"][0]["symbol"] == "BTC-USD"
    assert len(snap["crypto_leaders"]) == 3  # top list capped for UI; pulse uses full scan
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
    assert "llm_key_set" in snap["runtime"]
    assert "regime_gate" in snap["runtime"]
    assert "rs_gate" in snap["runtime"]
    assert "breadth_gate" in snap["runtime"]
    assert "calm_streak_days" in snap["runtime"]
    assert "calm_hint" in snap["runtime"]
    assert "stock_regime" in snap["runtime"]
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
    assert (tmp_path / "trader_config.json").exists()
    got = client.get("/desk/api/config")
    assert got.status_code == 200
    assert got.json()["ai_mode"] == "validate"


def test_desk_ops_has_config_form(tmp_path: Path, monkeypatch):
    _seed_portfolio(tmp_path)
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
    assert "Bitcoin" in client.get("/desk").text
    breadth = client.get("/desk/breadth")
    assert "Scan pulse" in breadth.text
    assert "Crypto A/D" in breadth.text
    assert "Recent days" in breadth.text
    assert 'id="pulse-key"' in breadth.text
    assert "breadth-days-table" in breadth.text
    assert "near-high" in breadth.text

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
                    "day": day,
                    "crypto_up": 1,
                    "crypto_down": 0,
                    "crypto_avg_chg": 1.0,
                    "crypto_big_movers": 0,
                    "stock_within_5pct_high": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    breadth2 = client.get("/desk/breadth")
    assert f"/desk/scan-log/{day}" in breadth2.text
    log_page = client.get(f"/desk/scan-log/{day}")
    assert log_page.status_code == 200
    assert "BTC-USD" in log_page.text
    assert client.get("/desk/scan-log/1999-01-01").status_code == 404
    book = client.get("/desk/book")
    assert "hold-spark" in book.text
    assert "average buy" in book.text.lower() or "avg cost" in book.text.lower()
    assert "+10.0%" in book.text
    ideas = client.get("/desk/ideas")
    assert "Paper candidates" in ideas.text
    assert "Adopted here" in ideas.text
    assert "No GitHub watch digest yet" in ideas.text  # seeded fixture has no watch file
    assert "d3.min.js" in client.get("/desk/charts").text
    assert "charts.js" in client.get("/desk/charts").text
    assert "hold-spark" in client.get("/desk/book").text
    assert "d3.min.js" in client.get("/desk/book").text
    assert "Buys / Sells" in client.get("/desk").text
    assert "unreal-spark" in client.get("/desk").text
    assert "ch-unreal" in client.get("/desk").text

    assert client.get("/desk/ops").text.find("Trader config") >= 0
    assert "AI mode" in client.get("/desk/ops").text
    assert "Live logs" in client.get("/desk/ops").text

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
