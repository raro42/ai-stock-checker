"""
Paper Desk — local web UI for ai-stock-checker.

Open http://127.0.0.1:7779/desk
JSON:  http://127.0.0.1:7779/desk/api
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from openbb_backend.symbol_names import display_name, resolve_symbol_names


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []
    return rows


def _fmt_hold(seconds: float) -> str:
    if seconds < 0:
        return "—"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


def _prices_from_scan(opp: dict[str, Any]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for key in ("crypto_leaders", "stock_breakouts"):
        for row in opp.get(key) or []:
            sym = row.get("symbol")
            px = row.get("price")
            if sym is not None and px is not None:
                try:
                    prices[str(sym)] = float(px)
                except (TypeError, ValueError):
                    continue
    return prices


def _fetch_yfinance_prices(
    symbols: list[str], timeout_s: float = 4.0
) -> dict[str, float]:
    if not symbols:
        return {}

    def _one(sym: str) -> tuple[str, Optional[float]]:
        try:
            import yfinance as yf

            t = yf.Ticker(sym)
            hist = t.history(period="1d")
            if hist is not None and not hist.empty:
                return sym, float(hist["Close"].iloc[-1])
            info = getattr(t, "fast_info", None)
            if info is not None:
                last = getattr(info, "last_price", None) or (
                    info.get("lastPrice") if hasattr(info, "get") else None
                )
                if last is not None:
                    return sym, float(last)
        except Exception:
            return sym, None
        return sym, None

    out: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(symbols))) as pool:
        futs = [pool.submit(_one, s) for s in symbols]
        deadline = time.time() + timeout_s
        for fut in futs:
            remaining = max(0.05, deadline - time.time())
            try:
                sym, px = fut.result(timeout=remaining)
                if px is not None and px > 0:
                    out[sym] = px
            except FuturesTimeout:
                continue
            except Exception:
                continue
    return out


def load_desk_snapshot(
    data_dir: Path,
    *,
    live_marks: Optional[bool] = None,
    price_fetcher: Optional[Callable[[list[str]], dict[str, float]]] = None,
) -> dict[str, Any]:
    """Build the paper desk view model from on-disk trader state."""
    if live_marks is None:
        live_marks = os.getenv("DESK_LIVE_MARKS", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }

    portfolio = _load_json(data_dir / "portfolio.json", {})
    trades = _load_jsonl(data_dir / "trades.jsonl")
    entry_times = _load_json(data_dir / "entry_times.json", {})
    scan_history = _load_json(data_dir / "stock_scan_history.json", {})
    scanned = _load_json(data_dir / "scanned_symbols.json", {})
    watchdog_path = data_dir / "watchdog" / "status.txt"
    watchdog = watchdog_path.read_text().strip() if watchdog_path.exists() else ""

    opp_path = data_dir / "archive" / "opportunities_latest.json"
    if not opp_path.exists():
        arch = data_dir / "archive"
        candidates = (
            sorted(arch.glob("opportunities_2*.json")) if arch.exists() else []
        )
        opp_path = candidates[-1] if candidates else opp_path
    opportunities = _load_json(opp_path, {})

    cash = float(portfolio.get("cash") or 0)
    initial = float(portfolio.get("initial_cash") or 0)
    fees = float(portfolio.get("total_fees_paid") or 0)
    commission_rate = float(portfolio.get("commission_rate") or 0.001)
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    now = time.time()

    scan_prices = _prices_from_scan(opportunities)
    marks = dict(scan_prices)
    mark_source = "scan" if scan_prices else "cost"
    missing = [s for s in holdings if s not in marks or marks[s] <= 0]
    if live_marks and missing:
        fetcher = price_fetcher or (
            lambda syms: _fetch_yfinance_prices(syms, timeout_s=4.0)
        )
        try:
            live = fetcher(missing)
            if live:
                marks.update(live)
                mark_source = "live+scan" if scan_prices else "live"
        except Exception:
            pass
    if not marks:
        mark_source = "cost"

    rows: list[dict[str, Any]] = []
    cost = 0.0
    market_value = 0.0
    for symbol, qty in holdings.items():
        q = float(qty)
        buy = float(avg.get(symbol, 0) or 0)
        basis = q * buy
        cost += basis
        last = marks.get(symbol)
        if last is None or last <= 0:
            last = buy
            marked = False
        else:
            marked = True
        mv = q * last
        market_value += mv
        unreal = mv - basis
        unreal_pct = (unreal / basis * 100) if basis else 0.0
        entry_ts = float(entry_times.get(symbol) or 0) or None
        held_s = (now - entry_ts) if entry_ts else None
        rows.append(
            {
                "symbol": symbol,
                "quantity": q,
                "avg_buy": buy,
                "cost_basis": basis,
                "last": last,
                "market_value": mv,
                "unrealized": unreal,
                "unrealized_pct": unreal_pct,
                "marked": marked,
                "kind": "crypto" if "-USD" in str(symbol) else "stock",
                "held": _fmt_hold(held_s) if held_s is not None else "—",
                "held_seconds": held_s,
                "bought_at": (
                    datetime.fromtimestamp(entry_ts, tz=timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                    if entry_ts
                    else ""
                ),
                "weight_pct": 0.0,
                "weight_bar_pct": 0.0,
            }
        )

    equity_cost = cash + cost
    equity_mtm = cash + market_value
    if any(r["marked"] for r in rows):
        equity = equity_mtm
    else:
        equity = equity_cost
        mark_source = "cost"

    ret_pct = ((equity / initial) - 1) * 100 if initial else 0.0
    unrealized_total = market_value - cost
    unrealized_pct = (unrealized_total / cost * 100) if cost else 0.0
    deployed_pct = ((equity - cash) / equity * 100) if equity else 0.0

    for r in rows:
        w = (r["market_value"] / equity * 100) if equity else 0.0
        r["weight_pct"] = w
        r["weight_bar_pct"] = min(max(w, 0.0), 100.0)
    rows.sort(key=lambda r: r["market_value"], reverse=True)

    sells = [t for t in trades if t.get("type") == "SELL"]
    buys = [t for t in trades if t.get("type") == "BUY"]
    realized = sum(float(t.get("profit_loss") or 0) for t in sells)

    recs_raw = (opportunities.get("recommendations") or [])[:8]
    crypto_raw = (opportunities.get("crypto_leaders") or [])[:6]
    stock_raw = (opportunities.get("stock_breakouts") or [])[:6]

    name_symbols: list[str] = []
    for sym in list(holdings.keys()):
        name_symbols.append(str(sym))
    for t in trades[-20:]:
        if t.get("symbol"):
            name_symbols.append(str(t["symbol"]))
    for r in recs_raw + crypto_raw + stock_raw:
        if r.get("symbol"):
            name_symbols.append(str(r["symbol"]))
    # unique, preserve order
    seen: set[str] = set()
    uniq_syms: list[str] = []
    for s in name_symbols:
        if s not in seen:
            seen.add(s)
            uniq_syms.append(s)
    names = resolve_symbol_names(uniq_syms, data_dir)

    for r in rows:
        r["name"] = display_name(r["symbol"], names)

    recent = []
    for t in reversed(trades[-20:]):
        sym = t.get("symbol") or "—"
        recent.append(
            {
                "timestamp": t.get("timestamp") or "—",
                "type": t.get("type") or "—",
                "symbol": sym,
                "name": display_name(str(sym), names),
                "quantity": float(t.get("quantity") or 0),
                "price": float(t.get("price") or 0),
                "commission": float(t.get("commission") or 0),
                "profit_loss": t.get("profit_loss"),
                "total_cost": t.get("total_cost"),
                "cash_remaining": t.get("cash_remaining"),
            }
        )

    recs = []
    for r in recs_raw:
        sym = r.get("symbol")
        recs.append(
            {
                "rank": r.get("rank"),
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "asset_class": r.get("asset_class"),
                "strategy": r.get("strategy"),
                "score": float(r.get("score") or 0),
                "reasoning": r.get("reasoning") or "",
            }
        )

    crypto_leaders = []
    for r in crypto_raw:
        sym = r.get("symbol")
        crypto_leaders.append(
            {
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "price": float(r.get("price") or 0),
                "change_24h": float(r.get("change_24h") or 0),
                "score": float(r.get("score") or 0),
                "volume_surge_pct": float(r.get("volume_surge_pct") or 0),
                "tradeable": bool(r.get("tradeable", True)),
            }
        )

    stock_breakouts = []
    for r in stock_raw:
        sym = r.get("symbol")
        stock_breakouts.append(
            {
                "symbol": sym,
                "name": display_name(str(sym or ""), names),
                "sector": r.get("sector") or "",
                "price": float(r.get("price") or 0),
                "pct_from_high": float(r.get("pct_from_high") or 0),
                "strength": r.get("strength") or "",
            }
        )

    scanned_count = len(scanned) if isinstance(scanned, dict) else 0
    hist_scanned = (
        scan_history.get("scanned") if isinstance(scan_history, dict) else {}
    )
    last_full = (
        scan_history.get("last_full_cycle") if isinstance(scan_history, dict) else None
    )
    weekend = datetime.now(timezone.utc).weekday() >= 5

    gh_watch = _load_json(data_dir / "github_watch" / "latest.json", {})
    gh_ideas = list(gh_watch.get("idea_bullets") or [])[:8]
    gh_updates = int(gh_watch.get("update_count") or 0)
    gh_at = gh_watch.get("generated_at") or ""

    return {
        "brand": "AI Stock Checker",
        "tagline": "Paper desk — honest marks, low churn.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "portfolio_updated": portfolio.get("last_updated") or "",
        "initial": initial,
        "cash": cash,
        "fees": fees,
        "commission_rate_pct": commission_rate * 100,
        "cost_basis_total": cost,
        "market_value": market_value,
        "equity": equity,
        "equity_cost": equity_cost,
        "ret_pct": ret_pct,
        "unrealized_total": unrealized_total,
        "unrealized_pct": unrealized_pct,
        "deployed_pct": deployed_pct,
        "positions": len(rows),
        "holdings": rows,
        "realized": realized,
        "trade_count": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "recent_trades": recent,
        "reset_note": portfolio.get("reset_note") or "",
        "weekend_mode": weekend,
        "weekend_hint": "Weekend: crypto-only trading; US stocks paused."
        if weekend
        else "Weekday session: stocks + crypto per scan rules.",
        "mark_source": mark_source,
        "mark_note": {
            "live": "Marks from live quotes + latest scan.",
            "live+scan": "Marks from live quotes + latest scan.",
            "scan": "Marks from latest scan prices (live quotes skipped/unavailable).",
            "cost": "Showing cost basis — no fresh marks yet.",
        }.get(mark_source, ""),
        "recommendations": recs,
        "crypto_leaders": crypto_leaders,
        "stock_breakouts": stock_breakouts,
        "scan_time": opportunities.get("scan_time") or "",
        "scanned_symbols": scanned_count,
        "scan_history_symbols": len(hist_scanned) if isinstance(hist_scanned, dict) else 0,
        "last_full_cycle": last_full or "",
        "watchdog": watchdog,
        "has_scan": bool(opportunities),
        "github_watch_at": gh_at,
        "github_watch_updates": gh_updates,
        "github_ideas": gh_ideas,
    }
