"""Chart series for the paper desk (equity, allocation, price history)."""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from openbb_backend.symbol_names import display_name, resolve_symbol_names


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return n if math.isfinite(n) else default


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


def _parse_trade_ts(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(raw[:26], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def build_equity_curve(data_dir: Path) -> list[dict[str, Any]]:
    """Book equity after each fill (cash + cost basis of open lots)."""
    portfolio = _load_json(data_dir / "portfolio.json", {})
    trades = _load_jsonl(data_dir / "trades.jsonl")
    initial = float(portfolio.get("initial_cash") or 0)
    cash = initial
    lots: dict[str, dict[str, float]] = {}  # symbol -> {qty, cost}
    points: list[dict[str, Any]] = []

    start_ts = None
    if trades:
        start_ts = _parse_trade_ts(str(trades[0].get("timestamp") or ""))
    if start_ts is None and portfolio.get("last_updated"):
        start_ts = _parse_trade_ts(str(portfolio["last_updated"]))
    if start_ts is None:
        start_ts = datetime.now(timezone.utc)

    points.append(
        {
            "t": start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "equity": round(initial, 2),
            "cash": round(initial, 2),
            "invested": 0.0,
            "label": "start",
        }
    )

    for trade in trades:
        side = str(trade.get("type") or "").upper()
        sym = str(trade.get("symbol") or "")
        qty = float(trade.get("quantity") or 0)
        price = float(trade.get("price") or 0)
        commission = float(trade.get("commission") or 0)
        ts = _parse_trade_ts(str(trade.get("timestamp") or "")) or start_ts

        if side == "BUY":
            total = qty * price + commission
            cash -= total
            lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
            lot["qty"] += qty
            lot["cost"] += qty * price
            if trade.get("cash_remaining") is not None:
                cash = float(trade["cash_remaining"])
        elif side == "SELL":
            lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
            avg = (lot["cost"] / lot["qty"]) if lot["qty"] else price
            proceeds = qty * price - commission
            cash += proceeds
            lot["qty"] = max(0.0, lot["qty"] - qty)
            lot["cost"] = max(0.0, lot["qty"] * avg)
            if lot["qty"] <= 1e-12:
                lots.pop(sym, None)
            if trade.get("cash_remaining") is not None:
                cash = float(trade["cash_remaining"])

        invested = sum(v["cost"] for v in lots.values())
        # Prefer live portfolio cash if this is the last trade
        equity = cash + invested
        points.append(
            {
                "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "equity": round(equity, 2),
                "cash": round(cash, 2),
                "invested": round(invested, 2),
                "label": f"{side} {sym}".strip(),
            }
        )

    # Anchor current book mark if available
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    if holdings:
        cash_now = float(portfolio.get("cash") or cash)
        invested_now = sum(
            float(q) * float(avg.get(s, 0) or 0) for s, q in holdings.items()
        )
        points.append(
            {
                "t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "equity": round(cash_now + invested_now, 2),
                "cash": round(cash_now, 2),
                "invested": round(invested_now, 2),
                "label": "now",
            }
        )
    return points


def build_allocation(data_dir: Path) -> list[dict[str, Any]]:
    from openbb_backend.desk import load_desk_snapshot

    # Cost/scan marks only — keep chart payload snappy.
    snap = load_desk_snapshot(
        data_dir,
        live_marks=False,
        price_fetcher=lambda _s: {},
    )
    # Prefer MTM weights from snapshot holdings
    rows = []
    for h in snap.get("holdings") or []:
        rows.append(
            {
                "symbol": h["symbol"],
                "name": h.get("name") or "",
                "value": round(float(h.get("market_value") or 0), 2),
                "weight_pct": round(float(h.get("weight_pct") or 0), 2),
                "kind": h.get("kind") or "stock",
            }
        )
    cash = float(snap.get("cash") or 0)
    equity = float(snap.get("equity") or 0) or 1.0
    rows.append(
        {
            "symbol": "CASH",
            "name": "Cash",
            "value": round(cash, 2),
            "weight_pct": round(cash / equity * 100, 2),
            "kind": "cash",
        }
    )
    rows.sort(key=lambda r: r["value"], reverse=True)
    return rows


def _cache_path(data_dir: Path, symbol: str) -> Path:
    safe = symbol.replace("/", "_")
    return data_dir / "chart_bars" / f"{safe}.json"


def fetch_price_history(
    symbol: str,
    data_dir: Path,
    *,
    days: int = 90,
    live: bool = True,
) -> list[dict[str, Any]]:
    """Daily closes for symbol; cached under data/chart_bars/."""
    path = _cache_path(data_dir, symbol)
    cached = _load_json(path, {})
    max_age = 6 * 3600

    def _clean(points: list) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in points or []:
            close = _finite(p.get("close"), default=float("nan"))
            if not math.isfinite(close):
                continue
            out.append({"t": p.get("t"), "close": round(close, 6)})
        return out

    if (
        cached.get("symbol") == symbol
        and cached.get("points")
        and (time.time() - float(cached.get("fetched_at") or 0)) < max_age
    ):
        cleaned = _clean(list(cached["points"]))
        if cleaned:
            return cleaned

    if not live:
        return _clean(list(cached.get("points") or []))

    try:
        import yfinance as yf

        period = "3mo" if days <= 100 else "6mo"
        hist = yf.Ticker(symbol).history(period=period)
        points: list[dict[str, Any]] = []
        if hist is not None and not hist.empty:
            for idx, row in hist.iterrows():
                try:
                    ts = idx.to_pydatetime().astimezone(timezone.utc)
                except Exception:
                    ts = datetime.now(timezone.utc)
                close = _finite(row.get("Close"), default=float("nan"))
                if not math.isfinite(close):
                    continue
                points.append(
                    {
                        "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "close": round(close, 6),
                    }
                )
        if points:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "symbol": symbol,
                        "fetched_at": time.time(),
                        "points": points,
                    }
                )
                + "\n"
            )
        return points
    except Exception:
        return _clean(list(cached.get("points") or []))


def build_price_panels(
    data_dir: Path, *, days: int = 90, live: Optional[bool] = None
) -> list[dict[str, Any]]:
    if live is None:
        live = os.getenv("DESK_CHART_LIVE", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holdings = list((portfolio.get("holdings") or {}).keys())
    # Also include top scan breakouts for color
    opp = _load_json(data_dir / "archive" / "opportunities_latest.json", {})
    extras = [
        r.get("symbol")
        for r in (opp.get("stock_breakouts") or [])[:4]
        if r.get("symbol")
    ]
    symbols: list[str] = []
    for s in holdings + extras:
        if s and s not in symbols:
            symbols.append(str(s))
    symbols = symbols[:8]
    names = resolve_symbol_names(symbols, data_dir, live=False)
    panels = []
    for sym in symbols:
        pts = fetch_price_history(sym, data_dir, days=days, live=live)
        if len(pts) < 2:
            continue
        base = _finite(pts[0]["close"])
        if base <= 0:
            continue
        indexed = []
        for p in pts:
            close = _finite(p["close"], default=float("nan"))
            if not math.isfinite(close):
                continue
            indexed.append(
                {
                    "t": p["t"],
                    "close": close,
                    "rebased": round(close / base * 100, 4),
                }
            )
        if len(indexed) < 2:
            continue
        last = indexed[-1]
        panels.append(
            {
                "symbol": sym,
                "name": display_name(sym, names) or sym,
                "points": indexed,
                "last": last["close"],
                "change_pct": round(last["rebased"] - 100, 2),
            }
        )
    return panels


def build_from_buy_panels(
    data_dir: Path, *, days: int = 180, live: Optional[bool] = None
) -> list[dict[str, Any]]:
    """Open lots rebased to avg buy (=100). Honest path since entry — no forecast."""
    if live is None:
        live = os.getenv("DESK_CHART_LIVE", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    entry_times = _load_json(data_dir / "entry_times.json", {})
    opportunities = _load_json(data_dir / "archive" / "opportunities_latest.json", {})
    from openbb_backend.desk import _prices_from_scan

    marks = _prices_from_scan(opportunities)
    symbols = [str(s) for s in holdings.keys() if s][:10]
    names = resolve_symbol_names(symbols, data_dir, live=False)
    panels: list[dict[str, Any]] = []

    for sym in symbols:
        buy_price = _finite(avg.get(sym))
        qty = _finite(holdings.get(sym))
        if buy_price <= 0 or qty <= 0:
            continue
        entry_raw = entry_times.get(sym)
        entry_ts = _finite(entry_raw) if entry_raw not in (None, "") else 0.0
        buy_dt: Optional[datetime] = None
        if entry_ts > 0:
            buy_dt = datetime.fromtimestamp(entry_ts, tz=timezone.utc)

        hist = fetch_price_history(sym, data_dir, days=days, live=live)
        pts: list[dict[str, Any]] = []
        for p in hist:
            ts = _parse_trade_ts(str(p.get("t") or ""))
            if ts is None:
                continue
            if buy_dt and ts < buy_dt:
                continue
            close = _finite(p.get("close"), default=float("nan"))
            if not math.isfinite(close) or close <= 0:
                continue
            pts.append({"t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "close": close})

        # Always anchor at the fill so short holds still chart.
        buy_iso = (
            buy_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if buy_dt
            else (pts[0]["t"] if pts else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        )
        if not pts or pts[0]["t"] > buy_iso:
            pts = [{"t": buy_iso, "close": buy_price}] + pts
        elif abs(pts[0]["close"] - buy_price) / buy_price > 0.02:
            # Prefer cost basis as the day-0 mark when history starts mid-hold.
            pts = [{"t": buy_iso, "close": buy_price}] + [
                p for p in pts if p["t"] > buy_iso
            ]

        # Prefer current scan mark as the right edge so short holds aren't a
        # flat cost→cost stub when the book already shows a different last.
        mark = _finite(marks.get(sym))
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if mark > 0:
            pts = [p for p in pts if p["t"] < now_iso]
            pts.append({"t": now_iso, "close": mark})
        elif len(pts) < 2:
            last_close = pts[0]["close"] if pts else buy_price
            if not pts:
                pts = [{"t": buy_iso, "close": buy_price}]
            if pts[-1]["t"] != now_iso:
                pts.append({"t": now_iso, "close": last_close})

        indexed = []
        for p in pts:
            close = _finite(p["close"])
            indexed.append(
                {
                    "t": p["t"],
                    "close": close,
                    "rebased": round(close / buy_price * 100, 4),
                }
            )
        last = indexed[-1]
        first_t = indexed[0]["t"]
        last_t = last["t"]
        span_hours = 0.0
        try:
            t0 = datetime.fromisoformat(first_t.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last_t.replace("Z", "+00:00"))
            span_hours = max(0.0, (t1 - t0).total_seconds() / 3600.0)
        except ValueError:
            span_hours = 0.0
        panels.append(
            {
                "symbol": sym,
                "name": display_name(sym, names) or sym,
                "buy_price": round(buy_price, 6),
                "bought_at": buy_iso,
                "quantity": qty,
                "points": indexed,
                "last": last["close"],
                "first_t": first_t,
                "last_t": last_t,
                "span_hours": round(span_hours, 2),
                "change_pct": round(last["rebased"] - 100, 2),
                "note": "Rebased to your avg buy (100). No forecast.",
            }
        )
    panels.sort(key=lambda p: abs(p["change_pct"]), reverse=True)
    return panels


def _apply_fill_to_lots(
    lots: dict[str, dict[str, float]], trade: dict[str, Any]
) -> None:
    side = str(trade.get("type") or "").upper()
    sym = str(trade.get("symbol") or "")
    if not sym:
        return
    qty = _finite(trade.get("quantity"))
    price = _finite(trade.get("price"))
    if qty <= 0 or price < 0:
        return
    if side == "BUY":
        lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
        lot["qty"] += qty
        lot["cost"] += qty * price
    elif side == "SELL":
        lot = lots.setdefault(sym, {"qty": 0.0, "cost": 0.0})
        avg = (lot["cost"] / lot["qty"]) if lot["qty"] else price
        lot["qty"] = max(0.0, lot["qty"] - qty)
        lot["cost"] = max(0.0, lot["qty"] * avg)
        if lot["qty"] <= 1e-12:
            lots.pop(sym, None)


def _lots_asof(
    timeline: list[tuple[datetime, dict[str, dict[str, float]]]], when: datetime
) -> dict[str, dict[str, float]]:
    state: dict[str, dict[str, float]] = {}
    for ts, snap in timeline:
        if ts <= when:
            state = snap
        else:
            break
    return {s: dict(v) for s, v in state.items()}


def _close_on_or_before(
    series: list[tuple[datetime, float]], when: datetime
) -> Optional[float]:
    px: Optional[float] = None
    for ts, close in series:
        if ts.date() <= when.date():
            px = close
        else:
            break
    return px


def build_unrealized_curve(
    data_dir: Path, *, days: int = 180, live: Optional[bool] = None
) -> list[dict[str, Any]]:
    """Open-book unrealized € / % vs cost (matches Overview). No forecast."""
    if live is None:
        live = os.getenv("DESK_CHART_LIVE", "1").strip() not in {
            "0",
            "false",
            "False",
            "no",
        }
    portfolio = _load_json(data_dir / "portfolio.json", {})
    holdings = portfolio.get("holdings") or {}
    avg = portfolio.get("avg_buy_price") or {}
    entry_times = _load_json(data_dir / "entry_times.json", {})
    lots: dict[str, dict[str, float]] = {}
    start_ts: Optional[datetime] = None
    for sym, qty in holdings.items():
        q = _finite(qty)
        buy = _finite(avg.get(sym))
        if q <= 0 or buy <= 0:
            continue
        lots[str(sym)] = {"qty": q, "cost": q * buy}
        entry_raw = entry_times.get(sym)
        entry_ts = _finite(entry_raw) if entry_raw not in (None, "") else 0.0
        if entry_ts > 0:
            dt = datetime.fromtimestamp(entry_ts, tz=timezone.utc)
            if start_ts is None or dt < start_ts:
                start_ts = dt

    # Fall back to trade replay when entry_times are missing.
    if not lots:
        trades = _load_jsonl(data_dir / "trades.jsonl")
        replay: dict[str, dict[str, float]] = {}
        for trade in trades:
            ts = _parse_trade_ts(str(trade.get("timestamp") or ""))
            if ts is None:
                continue
            _apply_fill_to_lots(replay, trade)
            if start_ts is None or ts < start_ts:
                start_ts = ts
        lots = replay

    if not lots:
        return []
    if start_ts is None:
        start_ts = datetime.now(timezone.utc)

    price_by_sym: dict[str, list[tuple[datetime, float]]] = {}
    day_set: set = set()
    for sym in lots:
        hist = fetch_price_history(sym, data_dir, days=max(days, 120), live=live)
        series: list[tuple[datetime, float]] = []
        for p in hist:
            ts = _parse_trade_ts(str(p.get("t") or ""))
            close = _finite(p.get("close"), default=float("nan"))
            if ts is None or not math.isfinite(close) or close <= 0:
                continue
            series.append((ts, close))
            day_set.add(ts.date())
        series.sort(key=lambda x: x[0])
        price_by_sym[sym] = series

    start_day = start_ts.date()
    days_sorted = sorted(d for d in day_set if d >= start_day)
    # Anchor at buy day even if bars start later.
    if start_day not in days_sorted:
        days_sorted = [start_day] + days_sorted

    points: list[dict[str, Any]] = []
    for day in days_sorted:
        when = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
        cost = 0.0
        market_value = 0.0
        active = 0
        for sym, v in lots.items():
            entry_raw = entry_times.get(sym)
            entry_ts = _finite(entry_raw) if entry_raw not in (None, "") else 0.0
            if entry_ts > 0:
                bought = datetime.fromtimestamp(entry_ts, tz=timezone.utc).date()
                if day < bought:
                    continue
            active += 1
            cost += v["cost"]
            px = _close_on_or_before(price_by_sym.get(sym) or [], when)
            if px is None:
                px = (v["cost"] / v["qty"]) if v["qty"] else 0.0
            market_value += v["qty"] * px
        if active == 0 or cost <= 0:
            continue
        unreal = market_value - cost
        points.append(
            {
                "t": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "unrealized": round(unreal, 2),
                "unrealized_pct": round((unreal / cost) * 100, 4),
                "cost": round(cost, 2),
                "market_value": round(market_value, 2),
            }
        )

    by_day: dict[str, dict[str, Any]] = {}
    for p in points:
        by_day[p["t"][:10]] = p
    return [by_day[k] for k in sorted(by_day)]


def load_chart_payload(data_dir: Path) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "equity": build_equity_curve(data_dir),
        "unrealized": build_unrealized_curve(data_dir),
        "allocation": build_allocation(data_dir),
        "prices": build_price_panels(data_dir),
        "from_buy": build_from_buy_panels(data_dir),
    }
